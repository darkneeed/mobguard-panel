from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any

from mobguard_platform import (
    DecisionBundle,
    build_auto_restriction_state,
    remote_access_squad_name,
    review_reason_for_bundle,
    should_warning_only,
)
from mobguard_platform.runtime_admin_defaults import ENFORCEMENT_SETTINGS_DEFAULTS
from mobguard_platform.storage.sqlite import is_sqlite_busy_error, is_sqlite_interrupted_error

from ..context import APIContainer
from .modules import _analyze_event, _build_batch_context, _remnawave_client, _resolve_remote_user
from .telegram_notifier import emit_ingest_notifications


logger = logging.getLogger(__name__)

INGEST_WORKER_NAME = "mobguard-ingest-worker"
ENFORCEMENT_DISPATCHER_NAME = "mobguard-enforcement-dispatcher"
INGEST_CLAIM_BATCH_SIZE = 25
ENFORCEMENT_CLAIM_BATCH_SIZE = 25
INGEST_CLAIM_TIMEOUT_SECONDS = 120
ENFORCEMENT_CLAIM_TIMEOUT_SECONDS = 120
INGEST_IDLE_SLEEP_SECONDS = 1.0
ENFORCEMENT_IDLE_SLEEP_SECONDS = 1.0
PIPELINE_SNAPSHOT_REFRESH_INTERVAL_SECONDS = 5.0
OVERVIEW_SNAPSHOT_REFRESH_INTERVAL_SECONDS = 15.0
HEARTBEAT_WRITE_INTERVAL_SECONDS = 15.0
INGEST_MAX_ATTEMPTS = 5
ENFORCEMENT_MAX_ATTEMPTS = 5


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _backoff_seconds(attempt_count: int) -> int:
    attempt = max(int(attempt_count), 1)
    return min(2 ** min(attempt, 5), 60)


def _is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, ValueError):
        return False
    if isinstance(exc, sqlite3.IntegrityError):
        return False
    return True


def _is_best_effort_sqlite_error(exc: BaseException) -> bool:
    return is_sqlite_busy_error(exc) or is_sqlite_interrupted_error(exc)


def _log_best_effort_skip(action: str, exc: BaseException) -> None:
    if is_sqlite_interrupted_error(exc):
        logger.debug("%s skipped because SQLite fast-read timed out", action)
        return
    logger.warning("%s skipped because SQLite is busy", action)


def _cache_decision_tx(conn: sqlite3.Connection, ip: str, bundle: DecisionBundle) -> None:
    expires = (datetime.utcnow().replace(microsecond=0) + timedelta(days=3)).isoformat()
    cache_payload = bundle.to_cache_payload()
    conn.execute(
        """
        INSERT OR REPLACE INTO ip_decisions (
            ip, status, confidence, details, asn, expires, log_json, bundle_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ip,
            cache_payload["status"],
            cache_payload["confidence"],
            cache_payload["details"],
            cache_payload.get("asn"),
            expires,
            json.dumps(cache_payload.get("log", []), ensure_ascii=False),
            json.dumps(cache_payload.get("bundle"), ensure_ascii=False),
        ),
    )


def _persist_behavior_state_tx(
    conn: sqlite3.Connection,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    bundle: DecisionBundle,
) -> None:
    uuid = str(user_data.get("uuid") or "").strip()
    tag = str(payload.get("tag") or "").strip()
    ip = str(payload.get("ip") or "").strip()
    if not uuid or not tag or not ip:
        return
    if bundle.source == "manual_override":
        return

    now = _utcnow()
    conn.execute(
        "INSERT INTO ip_history (uuid, ip, timestamp) VALUES (?, ?, ?)",
        (uuid, ip, now),
    )
    conn.execute(
        """
        INSERT INTO active_trackers (key, start_time, last_seen)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET last_seen = excluded.last_seen
        """,
        (f"{uuid}:{ip}", now, now),
    )
    if bundle.verdict not in {"MOBILE", "HOME"}:
        return
    subnet = ip.rsplit(".", 1)[0] if "." in ip else ip
    mobile = 1 if bundle.verdict == "MOBILE" else 0
    home = 1 if bundle.verdict == "HOME" else 0
    conn.execute(
        """
        INSERT INTO subnet_evidence (subnet, mobile_count, home_count, last_updated)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(subnet) DO UPDATE SET
            mobile_count = subnet_evidence.mobile_count + excluded.mobile_count,
            home_count = subnet_evidence.home_count + excluded.home_count,
            last_updated = excluded.last_updated
        """,
        (subnet, mobile, home, now),
    )


def _create_enforcement_job_tx(
    conn: sqlite3.Connection,
    *,
    event_uid: str,
    analysis_event_id: int,
    review_case_id: int | None,
    module_id: str | None,
    subject_uuid: str,
    job_type: str,
    payload: dict[str, Any],
) -> int:
    now = _utcnow()
    job_key = f"{event_uid}:{job_type}"
    cursor = conn.execute(
        """
        INSERT INTO enforcement_jobs (
            job_key, event_uid, analysis_event_id, review_case_id, module_id, subject_uuid,
            job_type, status, processing_owner, processing_started_at, attempt_count,
            next_attempt_at, last_error, last_error_at, applied_at, payload_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '', '', 0, ?, '', '', '', ?, ?, ?)
        ON CONFLICT(job_key) DO UPDATE SET
            payload_json = excluded.payload_json,
            updated_at = excluded.updated_at
        """,
        (
            job_key,
            event_uid,
            analysis_event_id,
            review_case_id,
            str(module_id or "").strip() or None,
            subject_uuid,
            job_type,
            now,
            json.dumps(payload, ensure_ascii=False),
            now,
            now,
        ),
    )
    if cursor.lastrowid:
        return int(cursor.lastrowid)
    row = conn.execute(
        "SELECT id FROM enforcement_jobs WHERE job_key = ?",
        (job_key,),
    ).fetchone()
    return int(row["id"]) if row else 0


def _plan_enforcement_tx(
    conn: sqlite3.Connection,
    runtime: Any,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    bundle: DecisionBundle,
    *,
    event_uid: str,
    analysis_event_id: int,
    review_case_id: int | None,
) -> dict[str, Any] | None:
    settings = runtime.settings
    if bundle.verdict != "HOME" or bundle.confidence_band not in {"HIGH_HOME", "PROBABLE_HOME"}:
        return None

    uuid = str(user_data.get("uuid") or "").strip()
    if not uuid:
        return None

    warning_only = (
        bool(settings.get("warning_only_mode", False))
        or bool(settings.get("shadow_mode", True))
        or should_warning_only(bundle)
        or not bundle.punitive_eligible
    )
    now_dt = datetime.utcnow().replace(microsecond=0)
    now = now_dt.isoformat()
    violation_row = conn.execute(
        """
        SELECT strikes, warning_count
        FROM violations
        WHERE uuid = ?
        """,
        (uuid,),
    ).fetchone()
    strikes = int(violation_row["strikes"]) if violation_row and violation_row["strikes"] is not None else 0
    warning_count = int(violation_row["warning_count"]) if violation_row and violation_row["warning_count"] is not None else 0

    if warning_only:
        next_warning_count = warning_count + 1
        conn.execute(
            """
            INSERT INTO violations (
                uuid, strikes, unban_time, last_forgiven, last_strike_time,
                warning_time, warning_count, restriction_mode,
                saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, 'SQUAD', NULL, NULL, NULL)
            ON CONFLICT(uuid) DO UPDATE SET
                warning_time = excluded.warning_time,
                warning_count = excluded.warning_count,
                last_strike_time = excluded.last_strike_time
            """,
            (
                uuid,
                strikes,
                now,
                now,
                now,
                next_warning_count,
            ),
        )
        return {
            "type": "warning",
            "warning_count": next_warning_count,
            "warning_only": True,
            "delivery_status": "applied",
        }

    durations = settings.get(
        "ban_durations_minutes",
        ENFORCEMENT_SETTINGS_DEFAULTS["ban_durations_minutes"],
    )
    if not isinstance(durations, list) or not durations:
        durations = ENFORCEMENT_SETTINGS_DEFAULTS["ban_durations_minutes"]
    next_strike = max(strikes, 0) + 1
    duration = int(durations[min(next_strike - 1, len(durations) - 1)])
    restriction_state = build_auto_restriction_state(user_data, settings)
    unban_time = (now_dt + timedelta(minutes=duration)).isoformat()
    conn.execute(
        """
        INSERT INTO violations (
            uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count,
            restriction_mode, saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
        ) VALUES (?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, ?)
        ON CONFLICT(uuid) DO UPDATE SET
            strikes = excluded.strikes,
            unban_time = excluded.unban_time,
            last_forgiven = excluded.last_forgiven,
            last_strike_time = excluded.last_strike_time,
            warning_time = NULL,
            warning_count = 0,
            restriction_mode = excluded.restriction_mode,
            saved_traffic_limit_bytes = excluded.saved_traffic_limit_bytes,
            saved_traffic_limit_strategy = excluded.saved_traffic_limit_strategy,
            applied_traffic_limit_bytes = excluded.applied_traffic_limit_bytes
        """,
        (
            uuid,
            next_strike,
            unban_time,
            now,
            now,
            restriction_state["restriction_mode"],
            restriction_state["saved_traffic_limit_bytes"],
            restriction_state["saved_traffic_limit_strategy"],
            restriction_state["applied_traffic_limit_bytes"],
        ),
    )
    conn.execute(
        """
        INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid,
            str(payload.get("ip") or ""),
            str(bundle.isp or ""),
            bundle.asn,
            str(payload.get("tag") or ""),
            next_strike,
            duration,
            now,
        ),
    )

    dry_run = bool(settings.get("dry_run", True))
    remote_change_required = bool(restriction_state.get("remote_change_required", True))
    delivery_status = "applied" if dry_run or not remote_change_required else "pending"
    job_id = 0
    if not dry_run and remote_change_required:
        job_type = "traffic_cap" if restriction_state["restriction_mode"] == "TRAFFIC_CAP" else "access_state"
        job_payload = {
            "uuid": uuid,
            "restriction_mode": restriction_state["restriction_mode"],
            "restricted_squad_name": remote_access_squad_name(settings, restricted=True),
            "applied_traffic_limit_bytes": restriction_state.get("applied_traffic_limit_bytes"),
            "traffic_limit_strategy": restriction_state.get("saved_traffic_limit_strategy")
            or user_data.get("trafficLimitStrategy")
            or "NO_RESET",
        }
        job_id = _create_enforcement_job_tx(
            conn,
            event_uid=event_uid,
            analysis_event_id=analysis_event_id,
            review_case_id=review_case_id,
            module_id=str(user_data.get("module_id") or "").strip() or None,
            subject_uuid=uuid,
            job_type=job_type,
            payload=job_payload,
        )

    return {
        "type": "ban",
        "strike": next_strike,
        "ban_minutes": duration,
        "delivery_status": delivery_status,
        "job_id": job_id or None,
        "dry_run": dry_run,
        "warning_only": False,
    }


async def _process_claimed_event(
    container: APIContainer,
    runtime: Any,
    module: dict[str, Any],
    claimed_row: dict[str, Any],
) -> dict[str, Any]:
    event_uid = str(claimed_row.get("event_uid") or "").strip()
    try:
        payload = json.loads(str(claimed_row.get("raw_payload_json") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Raw event {event_uid} has invalid payload JSON") from exc
    payload["event_uid"] = event_uid

    raw_ip = str(payload.get("ip") or "").strip()
    if not raw_ip:
        raise ValueError("Raw event is missing ip")

    user_data = await _resolve_remote_user(runtime, payload)
    user_data["module_id"] = module["module_id"]
    user_data["module_name"] = module["module_name"]

    system_id = user_data.get("id")
    telegram_id = user_data.get("telegramId")
    if system_id is not None and int(system_id) in runtime.exempt_ids:
        with container.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE ingested_raw_events
                SET processing_state = 'processed',
                    processing_owner = '',
                    processing_started_at = '',
                    processed_at = ?
                WHERE event_uid = ?
                """,
                (_utcnow(), event_uid),
            )
            conn.commit()
        return {"status": "skipped", "reason": "exempt_system_id", "event_uid": event_uid}
    if telegram_id not in (None, "") and int(telegram_id) in runtime.exempt_tg_ids:
        with container.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE ingested_raw_events
                SET processing_state = 'processed',
                    processing_owner = '',
                    processing_started_at = '',
                    processed_at = ?
                WHERE event_uid = ?
                """,
                (_utcnow(), event_uid),
            )
            conn.commit()
        return {"status": "skipped", "reason": "exempt_telegram_id", "event_uid": event_uid}

    manual_override = await container.store.async_get_ip_override(raw_ip)
    cached = None
    if not manual_override:
        manual_override = await container.analysis_store.get_unsure_pattern(raw_ip)
    if not manual_override:
        cached = await container.analysis_store.get_cached_decision(raw_ip)

    live_analyzed = False
    if cached:
        bundle = DecisionBundle.from_cache_record(raw_ip, cached)
    else:
        bundle = await _analyze_event(
            runtime,
            user_data,
            payload,
            persist_behavior_state=False,
            persist_decision=False,
        )
        live_analyzed = True

    review_reason = review_reason_for_bundle(bundle)

    with container.store._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing_event = conn.execute(
            """
            SELECT id
            FROM analysis_events
            WHERE source_event_uid = ?
            """,
            (event_uid,),
        ).fetchone()
        if existing_event:
            event_id = int(existing_event["id"])
            review_case_row = conn.execute(
                """
                SELECT id
                FROM review_cases
                WHERE latest_event_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (event_id,),
            ).fetchone()
            review_case_id = int(review_case_row["id"]) if review_case_row else None
            conn.execute(
                """
                UPDATE ingested_raw_events
                SET processing_state = 'processed',
                    processing_owner = '',
                    processing_started_at = '',
                    processed_at = ?,
                    analysis_event_id = ?,
                    review_case_id = ?
                WHERE event_uid = ?
                """,
                (_utcnow(), event_id, review_case_id, event_uid),
            )
            conn.commit()
            return {
                "status": "processed",
                "event_id": event_id,
                "review_case_id": review_case_id,
                "review_reason": review_reason,
                "bundle": bundle.to_dict(),
                "event_uid": event_uid,
            }

        if live_analyzed:
            _cache_decision_tx(conn, raw_ip, bundle)
            _persist_behavior_state_tx(conn, user_data, payload, bundle)

        event_id = container.store.review_admin._record_analysis_event(
            conn,
            user_data,
            raw_ip,
            str(payload.get("tag") or ""),
            bundle,
            observation={
                "client_device_id": payload.get("client_device_id"),
                "client_device_label": payload.get("client_device_label"),
                "client_os_family": payload.get("client_os_family"),
                "client_os_version": payload.get("client_os_version"),
                "client_app_name": payload.get("client_app_name"),
                "client_app_version": payload.get("client_app_version"),
            },
            source_event_uid=event_uid,
        )
        bundle.event_id = event_id

        review_case_id: int | None = None
        if review_reason:
            review_case = container.store.review_admin._ensure_review_case(
                conn,
                user_data,
                raw_ip,
                str(payload.get("tag") or ""),
                bundle,
                event_id,
                review_reason,
            )
            review_case_id = review_case.id
            bundle.case_id = review_case_id

        enforcement = _plan_enforcement_tx(
            conn,
            runtime,
            user_data,
            payload,
            bundle,
            event_uid=event_uid,
            analysis_event_id=event_id,
            review_case_id=review_case_id,
        )

        conn.execute(
            """
            UPDATE ingested_raw_events
            SET processing_state = 'processed',
                processing_owner = '',
                processing_started_at = '',
                processed_at = ?,
                analysis_event_id = ?,
                review_case_id = ?
            WHERE event_uid = ?
            """,
            (_utcnow(), event_id, review_case_id, event_uid),
        )
        conn.commit()

    result = {
        "status": "processed",
        "event_id": event_id,
        "review_case_id": review_case_id,
        "review_reason": review_reason,
        "bundle": bundle.to_dict(),
        "enforcement": enforcement,
        "event_uid": event_uid,
    }
    await emit_ingest_notifications(
        container,
        user_data,
        bundle,
        str(payload.get("tag") or ""),
        review_reason,
        enforcement,
    )
    return result


async def process_ingest_batch_once(
    container: APIContainer,
    *,
    owner: str | None = None,
    limit: int = INGEST_CLAIM_BATCH_SIZE,
) -> dict[str, Any]:
    worker_owner = owner or f"{INGEST_WORKER_NAME}:{os.getpid()}"
    claimed_rows = await asyncio.to_thread(
        container.store.claim_raw_events,
        worker_owner,
        limit=limit,
        claim_timeout_seconds=INGEST_CLAIM_TIMEOUT_SECONDS,
    )
    if not claimed_rows:
        return {"claimed": 0, "processed": 0, "retried": 0, "failed": 0}

    runtime_cache: dict[str, tuple[dict[str, Any], Any]] = {}
    summary = {"claimed": len(claimed_rows), "processed": 0, "retried": 0, "failed": 0}

    for row in claimed_rows:
        module_id = str(row.get("module_id") or "").strip()
        module_name = str(row.get("module_name") or "").strip() or module_id
        if module_id not in runtime_cache:
            module = container.store.get_module(module_id) or {"module_id": module_id, "module_name": module_name}
            runtime_cache[module_id] = (module, _build_batch_context(container, module))
        module, runtime = runtime_cache[module_id]
        try:
            await _process_claimed_event(container, runtime, module, row)
            summary["processed"] += 1
        except Exception as exc:
            attempts = int(row.get("attempt_count") or 0)
            transient = _is_transient_error(exc)
            dead_letter = (not transient) or attempts >= INGEST_MAX_ATTEMPTS
            next_attempt_at = (
                datetime.utcnow().replace(microsecond=0) + timedelta(seconds=_backoff_seconds(attempts))
            ).isoformat()
            await asyncio.to_thread(
                container.store.mark_raw_event_retry,
                str(row.get("event_uid") or ""),
                next_attempt_at=next_attempt_at,
                error_text=str(exc),
                dead_letter=dead_letter,
            )
            summary["failed" if dead_letter else "retried"] += 1
            logger.exception("Queued ingest event failed: event_uid=%s", row.get("event_uid"))

    container.store.mark_ingest_pipeline_snapshot_dirty()
    return summary


def _dispatch_remote_job(container: APIContainer, job: dict[str, Any]) -> None:
    payload = json.loads(str(job.get("payload_json") or "{}"))
    job_type = str(job.get("job_type") or "").strip()
    uuid = str(payload.get("uuid") or "").strip()
    if not uuid:
        raise ValueError("Enforcement job is missing uuid")
    client = _remnawave_client(container)
    if not client.enabled:
        raise RuntimeError("Remnawave client is disabled")

    if job_type == "access_state":
        squad_name = str(payload.get("restricted_squad_name") or "").strip()
        if not squad_name:
            raise ValueError("Enforcement job is missing restricted squad name")
        remote_updated = bool(client.apply_access_squad(uuid, squad_name))
    elif job_type == "traffic_cap":
        remote_updated = bool(
            client.update_user_traffic_limit(
                uuid,
                int(payload.get("applied_traffic_limit_bytes") or 0),
                str(payload.get("traffic_limit_strategy") or "NO_RESET"),
            )
        )
    else:
        raise ValueError(f"Unsupported enforcement job type: {job_type}")

    if not remote_updated:
        raise RuntimeError(client.last_error or "Remote enforcement update failed")


async def dispatch_enforcement_batch_once(
    container: APIContainer,
    *,
    owner: str | None = None,
    limit: int = ENFORCEMENT_CLAIM_BATCH_SIZE,
) -> dict[str, Any]:
    dispatcher_owner = owner or f"{ENFORCEMENT_DISPATCHER_NAME}:{os.getpid()}"
    claimed_jobs = await asyncio.to_thread(
        container.store.claim_enforcement_jobs,
        dispatcher_owner,
        limit=limit,
        claim_timeout_seconds=ENFORCEMENT_CLAIM_TIMEOUT_SECONDS,
    )
    if not claimed_jobs:
        return {"claimed": 0, "applied": 0, "retried": 0, "failed": 0}

    summary = {"claimed": len(claimed_jobs), "applied": 0, "retried": 0, "failed": 0}
    for job in claimed_jobs:
        job_id = int(job["id"])
        try:
            await asyncio.to_thread(_dispatch_remote_job, container, job)
            await asyncio.to_thread(container.store.mark_enforcement_job_applied, job_id)
            summary["applied"] += 1
        except Exception as exc:
            attempts = int(job.get("attempt_count") or 0)
            transient = _is_transient_error(exc)
            dead_letter = (not transient) or attempts >= ENFORCEMENT_MAX_ATTEMPTS
            next_attempt_at = (
                datetime.utcnow().replace(microsecond=0) + timedelta(seconds=_backoff_seconds(attempts))
            ).isoformat()
            await asyncio.to_thread(
                container.store.mark_enforcement_job_retry,
                job_id,
                next_attempt_at=next_attempt_at,
                error_text=str(exc),
                dead_letter=dead_letter,
            )
            summary["failed" if dead_letter else "retried"] += 1
            logger.exception("Enforcement job failed: id=%s", job_id)

    container.store.mark_ingest_pipeline_snapshot_dirty()
    return summary


async def ingest_worker_loop(container: APIContainer) -> None:
    last_overview_snapshot_refresh = 0.0
    last_heartbeat_write = 0.0
    while True:
        summary = await process_ingest_batch_once(container)
        now = time.monotonic()
        pipeline_snapshot_result = await asyncio.to_thread(container.store.refresh_due_ingest_pipeline_snapshot)
        if pipeline_snapshot_result.get("busy"):
            logger.warning("Pipeline snapshot refresh skipped because SQLite is busy")
        if now - last_overview_snapshot_refresh >= OVERVIEW_SNAPSHOT_REFRESH_INTERVAL_SECONDS:
            try:
                await asyncio.to_thread(container.store.refresh_overview_snapshot, low_priority=True)
            except sqlite3.OperationalError as exc:
                if _is_best_effort_sqlite_error(exc):
                    _log_best_effort_skip("Overview snapshot refresh", exc)
                else:
                    logger.exception("Overview snapshot refresh failed")
            except Exception:
                logger.exception("Overview/pipeline snapshot refresh failed")
            last_overview_snapshot_refresh = now
        if now - last_heartbeat_write >= HEARTBEAT_WRITE_INTERVAL_SECONDS:
            try:
                await asyncio.to_thread(
                    container.store.update_service_heartbeat,
                    INGEST_WORKER_NAME,
                    "ok",
                    {
                        "claimed": summary["claimed"],
                        "processed": summary["processed"],
                        "retried": summary["retried"],
                        "failed": summary["failed"],
                    },
                    low_priority=True,
                )
            except sqlite3.OperationalError as exc:
                if _is_best_effort_sqlite_error(exc):
                    _log_best_effort_skip("Ingest worker heartbeat update", exc)
                else:
                    logger.exception("Failed to update ingest worker heartbeat")
            except Exception:
                logger.exception("Failed to update ingest worker heartbeat")
            last_heartbeat_write = now
        if summary["claimed"] == 0:
            await asyncio.sleep(INGEST_IDLE_SLEEP_SECONDS)


async def enforcement_dispatcher_loop(container: APIContainer) -> None:
    last_heartbeat_write = 0.0
    while True:
        summary = await dispatch_enforcement_batch_once(container)
        pipeline_snapshot_result = await asyncio.to_thread(container.store.refresh_due_ingest_pipeline_snapshot)
        if pipeline_snapshot_result.get("busy"):
            logger.warning("Pipeline snapshot refresh skipped because SQLite is busy")
        now = time.monotonic()
        if now - last_heartbeat_write >= HEARTBEAT_WRITE_INTERVAL_SECONDS:
            try:
                await asyncio.to_thread(
                    container.store.update_service_heartbeat,
                    ENFORCEMENT_DISPATCHER_NAME,
                    "ok",
                    {
                        "claimed": summary["claimed"],
                        "applied": summary["applied"],
                        "retried": summary["retried"],
                        "failed": summary["failed"],
                    },
                    low_priority=True,
                )
            except sqlite3.OperationalError as exc:
                if _is_best_effort_sqlite_error(exc):
                    _log_best_effort_skip("Enforcement dispatcher heartbeat update", exc)
                else:
                    logger.exception("Failed to update enforcement dispatcher heartbeat")
            except Exception:
                logger.exception("Failed to update enforcement dispatcher heartbeat")
            last_heartbeat_write = now
        if summary["claimed"] == 0:
            await asyncio.sleep(ENFORCEMENT_IDLE_SLEEP_SECONDS)
