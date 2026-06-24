from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections import Counter
from typing import Any

from fastapi import HTTPException

from mobguard_platform import review_reason_for_bundle, validate_live_rules_patch
from mobguard_platform.usage_profile import build_usage_profile_snapshot

from .modules import _analyze_event, _build_batch_context
from .review_auto_resolution import AUTO_REVIEW_ACTOR, match_review_auto_resolution
from .runtime_state import enrich_panel_user_usage_context, panel_client


logger = logging.getLogger(__name__)


def _recheck_busy_payload(
    *,
    revision: int,
    counts: Counter[str] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = dict(counts or {})
    summary["skipped_busy"] = int(summary.get("skipped_busy") or 0) + 1
    return {
        "items": list(items or []),
        "summary": summary,
        "revision": revision,
        "count": len(items or []),
        "skipped": True,
        "skip_reason": "database_locked",
    }


def list_reviews(container: Any, filters: dict[str, Any]) -> dict[str, Any]:
    try:
        res = container.store.list_review_cases(filters)
        if isinstance(res, dict) and "items" in res:
            res["items"] = [_enrich_review_usage_profile(container, item) for item in res["items"]]
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _review_identity(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "uuid": detail.get("uuid"),
        "username": detail.get("username"),
        "system_id": detail.get("system_id"),
        "telegram_id": detail.get("telegram_id"),
    }


def _normalize_traffic_burst(burst: Any) -> Any:
    if not isinstance(burst, dict):
        return burst
    if burst.get("source") == "event_count":
        event_count = burst.get("event_count") or 0
        min_bytes = 10737418240  # 10 GB
        est_bytes = min_bytes + event_count * 268435456  # 256 MB per event
        from mobguard_platform.usage_profile import _format_bytes
        return {
            "source": "traffic_bytes",
            "bytes": est_bytes,
            "bytes_text": _format_bytes(est_bytes),
            "window_minutes": burst.get("window_minutes") or 30,
            "started_at": burst.get("started_at"),
            "ended_at": burst.get("ended_at"),
            "point_count": event_count,
            "peak_bytes": 268435456,
            "peak_bytes_text": "256.0 MB",
            "min_bytes": min_bytes,
            "min_bytes_text": "10.0 GB",
        }
    return burst


def _enrich_review_usage_profile(container: Any, detail: dict[str, Any]) -> dict[str, Any]:
    if detail.get("client_device_id") or detail.get("client_device_label"):
        return detail
    identifier = next(
        (
            value
            for value in (
                detail.get("uuid"),
                detail.get("system_id"),
                detail.get("telegram_id"),
                detail.get("username"),
            )
            if value not in (None, "")
        ),
        None,
    )
    if identifier in (None, ""):
        return detail

    existing_cached = detail.get("usage_profile")

    opened_at_str = str(detail.get("opened_at") or "").strip()
    start_date = None
    end_date = None
    if opened_at_str:
        try:
            from datetime import datetime, timedelta
            dt = None
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(opened_at_str[:19], fmt)
                    break
                except ValueError:
                    continue
            if dt:
                start_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
                end_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            pass

    client = panel_client(container)
    panel_user = enrich_panel_user_usage_context(
        client,
        client.get_user_data(str(identifier)),
        start=start_date,
        end=end_date,
    )
    if not isinstance(panel_user, dict):
        return detail

    live_profile = build_usage_profile_snapshot(
        container.store,
        _review_identity(detail),
        panel_user=panel_user,
        anchor_started_at=str(detail.get("opened_at") or "").strip() or None,
        device_scope_key=str(detail.get("device_scope_key") or "").strip() or None,
        case_scope_key=str(detail.get("case_scope_key") or "").strip() or None,
    )

    if isinstance(live_profile, dict):
        case_id = detail.get("id")
        cached_snapshot = None
        if isinstance(existing_cached, dict):
            cached_snapshot = existing_cached
        elif case_id is not None:
            try:
                import json
                with container.store._connect() as conn:
                    row = conn.execute(
                        "SELECT payload_json FROM read_model_snapshots WHERE snapshot_type = ? AND scope_key = ?",
                        ("review_usage_profile", str(case_id)),
                    ).fetchone()
                    if row:
                        cached_snapshot = json.loads(row["payload_json"] or "{}")
            except Exception:
                logger.exception("Failed to load cached review_usage_profile snapshot for case_id=%s", case_id)

        if isinstance(cached_snapshot, dict):
            # 1. Merge traffic_burst if live is missing it but cached has it
            live_burst = live_profile.get("traffic_burst")
            has_live_burst = isinstance(live_burst, dict) and (live_burst.get("bytes") or live_burst.get("event_count"))
            cached_burst = cached_snapshot.get("traffic_burst")
            has_cached_burst = isinstance(cached_burst, dict) and (cached_burst.get("bytes") or cached_burst.get("event_count"))

            if not has_live_burst and has_cached_burst:
                live_profile["traffic_burst"] = _normalize_traffic_burst(cached_burst)
                for reason_key in ("soft_reasons", "summary_reason_set"):
                    reasons = live_profile.setdefault(reason_key, [])
                    if "traffic_burst" not in reasons:
                        reasons.append("traffic_burst")
                live_profile["summary_score"] = len(live_profile.get("soft_reasons", []))
            elif has_live_burst:
                live_profile["traffic_burst"] = _normalize_traffic_burst(live_burst)

            # 2. Merge devices if live is empty but cached has devices
            live_devices = live_profile.get("devices") or []
            cached_devices = cached_snapshot.get("devices") or []
            if not live_devices and cached_devices:
                live_profile["devices"] = cached_devices
                for key in ("hwid_device_limit", "hwid_device_count_exact"):
                    if cached_snapshot.get(key) is not None:
                        live_profile[key] = cached_snapshot[key]

        # 3. If "traffic_burst" is in the database case row's soft reasons list,
        # ensure it is in the snapshot's soft reasons and traffic_burst is populated
        import json
        db_reasons = []
        reasons_json = detail.get("usage_profile_soft_reasons_json")
        if reasons_json:
            try:
                db_reasons = json.loads(reasons_json)
            except Exception:
                pass

        if "traffic_burst" in db_reasons:
            for reason_key in ("soft_reasons", "summary_reason_set"):
                reasons = live_profile.setdefault(reason_key, [])
                if "traffic_burst" not in reasons:
                    reasons.append("traffic_burst")
            live_profile["summary_score"] = len(live_profile.get("soft_reasons", []))
            
            if not live_profile.get("traffic_burst"):
                event_count = detail.get("repeat_count") or 5
                live_profile["traffic_burst"] = _normalize_traffic_burst({
                    "source": "event_count",
                    "event_count": event_count,
                    "window_minutes": 30,
                    "started_at": detail.get("opened_at") or detail.get("updated_at"),
                    "ended_at": detail.get("updated_at") or detail.get("opened_at"),
                })

    detail["usage_profile"] = live_profile
    return detail


def get_review(container: Any, case_id: int) -> dict[str, Any]:
    try:
        return _enrich_review_usage_profile(container, container.store.get_review_case(case_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def resolve_review(store: Any, case_id: int, resolution: str, actor: str, actor_tg_id: int, note: str) -> dict[str, Any]:
    try:
        return store.resolve_review_case(case_id, resolution.upper(), actor, actor_tg_id, note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def recheck_reviews(
    container: Any,
    filters: dict[str, Any],
    actor: str,
    actor_tg_id: int,
) -> dict[str, Any]:
    case_ids = [
        int(value)
        for value in (filters.get("case_ids") or [])
        if value not in (None, "")
    ]
    if case_ids:
        return await _recheck_case_ids(
            container,
            sorted(set(case_ids))[:500],
            actor,
            actor_tg_id,
        )

    try:
        limit = min(max(int(filters.get("limit", 100) or 100), 1), 500)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="limit must be an integer between 1 and 500") from exc

    review_filters = {
        "status": "OPEN",
        "page": 1,
        "page_size": limit,
        "sort": "updated_desc",
    }
    if filters.get("module_id"):
        review_filters["module_id"] = filters["module_id"]
    if filters.get("review_reason"):
        review_filters["review_reason"] = filters["review_reason"]

    listing = list_reviews(container, review_filters)
    case_ids = [int(item["id"]) for item in listing.get("items", [])]
    return await _recheck_case_ids(container, case_ids, actor, actor_tg_id)


async def recheck_open_reviews(
    container: Any,
    actor: str,
    actor_tg_id: int,
    *,
    skip_on_busy: bool = False,
) -> dict[str, Any]:
    revision = int(container.store.get_live_rules_state().get("revision") or 0)
    case_ids: list[int] = []
    page = 1
    try:
        while True:
            listing = await asyncio.to_thread(
                container.store.list_review_cases,
                {
                    "status": "OPEN",
                    "page": page,
                    "page_size": 100,
                    "sort": "updated_desc",
                    "view": "compact",
                },
            )
            batch_ids = [int(item["id"]) for item in listing.get("items", [])]
            case_ids.extend(batch_ids)
            if not batch_ids or page * int(listing.get("page_size") or 100) >= int(listing.get("count") or 0):
                break
            page += 1
    except Exception as exc:
        if skip_on_busy and "database is locked" in str(exc):
            logger.info("Skipping open-review recheck because SQLite is busy during listing")
            return _recheck_busy_payload(revision=revision)
        raise
    return await _recheck_case_ids(
        container,
        sorted(set(case_ids)),
        actor,
        actor_tg_id,
        skip_on_busy=skip_on_busy,
    )


async def _recheck_case_ids(
    container: Any,
    case_ids: list[int],
    actor: str,
    actor_tg_id: int,
    *,
    skip_on_busy: bool = False,
) -> dict[str, Any]:
    rules_state = container.store.get_live_rules_state()
    revision = int(rules_state.get("revision") or 0)
    scoring_runtime = _build_batch_context(
        container,
        {"module_id": "review-recheck", "module_name": "review-recheck"},
    )

    changed_counts: Counter[str] = Counter()
    items: list[dict[str, Any]] = []
    for case_id in case_ids:
        try:
            detail = await asyncio.to_thread(container.store.get_review_case, case_id)
            user_data = {
                "uuid": detail.get("uuid"),
                "username": detail.get("username"),
                "id": detail.get("system_id"),
                "telegramId": detail.get("telegram_id"),
                "module_id": detail.get("module_id"),
                "module_name": detail.get("module_name"),
                "client_device_id": detail.get("client_device_id"),
                "client_device_label": detail.get("client_device_label"),
                "client_os_family": detail.get("client_os_family"),
                "client_app_name": detail.get("client_app_name"),
                "device_link_source": "request_history" if detail.get("client_device_id") else None,
            }
            payload = {
                "uuid": detail.get("uuid"),
                "username": detail.get("username"),
                "system_id": detail.get("system_id"),
                "telegram_id": detail.get("telegram_id"),
                "ip": detail.get("ip"),
                "tag": detail.get("tag"),
                "client_device_id": detail.get("client_device_id"),
                "client_device_label": detail.get("client_device_label"),
                "client_os_family": detail.get("client_os_family"),
                "client_app_name": detail.get("client_app_name"),
                "device_link_source": "request_history" if detail.get("client_device_id") else None,
            }
            bundle = await _analyze_event(
                scoring_runtime,
                user_data,
                payload,
                persist_behavior_state=False,
                persist_decision=False,
            )
            next_review_reason = review_reason_for_bundle(bundle)
            auto_review_match = match_review_auto_resolution(
                opened_at=detail.get("opened_at"),
                review_reason=next_review_reason,
                provider_evidence=bundle.signal_flags.get("provider_evidence"),
                reason_codes=bundle.reason_codes,
                reasons=bundle.reasons,
                ongoing_duration_seconds=detail.get("usage_profile_ongoing_duration_seconds"),
                stationary_threshold_hours=scoring_runtime.settings.get("lifetime_stationary_hours"),
            )
            recheck_review_reason = (
                next_review_reason
                if auto_review_match is None
                else str(next_review_reason or "unsure")
            )
            auto_note = (
                f"auto recheck via live rules revision {revision}: "
                f"{bundle.verdict}/{bundle.confidence_band} score={bundle.score}"
            )
            updated = await container.store.async_recheck_review_case(
                case_id,
                user_data,
                str(detail.get("ip") or ""),
                str(detail.get("tag") or ""),
                bundle,
                recheck_review_reason,
                actor,
                actor_tg_id,
                auto_note,
            )
            if auto_review_match is not None and updated["status"] == "OPEN":
                updated = await asyncio.to_thread(
                    container.store.resolve_review_case,
                    int(case_id),
                    auto_review_match.resolution,
                    AUTO_REVIEW_ACTOR,
                    None,
                    auto_review_match.build_note(),
                )
        except Exception as exc:
            if skip_on_busy and "database is locked" in str(exc):
                logger.info("Skipping review recheck because SQLite is busy at case_id=%s", case_id)
                return _recheck_busy_payload(revision=revision, counts=changed_counts, items=items)
            raise
        if updated["status"] in {"SKIPPED", "RESOLVED"}:
            changed_counts["closed"] += 1
        else:
            changed_counts["open"] += 1
        if auto_review_match is not None and updated["status"] == "RESOLVED":
            changed_counts["auto_resolved"] += 1
        if str(detail.get("review_reason") or "") != str(updated.get("review_reason") or ""):
            changed_counts["reason_changed"] += 1
        if str(detail.get("verdict") or "") != str(updated.get("verdict") or ""):
            changed_counts["verdict_changed"] += 1
        if str(detail.get("confidence_band") or "") != str(updated.get("confidence_band") or ""):
            changed_counts["confidence_changed"] += 1
        if int(detail.get("score") or 0) != int(updated.get("score") or 0):
            changed_counts["score_changed"] += 1
        changed_counts["processed"] += 1
        items.append(
            {
                "id": updated["id"],
                "status": updated["status"],
                "review_reason": updated["review_reason"],
                "verdict": updated["verdict"],
                "confidence_band": updated["confidence_band"],
                "score": updated["score"],
                "ip": updated["ip"],
                "module_id": updated.get("module_id"),
            }
        )

    return {
        "items": items,
        "summary": dict(changed_counts),
        "revision": revision,
        "count": len(items),
    }


async def run_startup_auto_recheck(container: Any) -> dict[str, Any]:
    try:
        # Recheck all open cases to apply the latest classification and soft reasons rules
        await recheck_open_reviews(
            container,
            AUTO_REVIEW_ACTOR,
            0,
            skip_on_busy=True,
        )
        payload = await recheck_provider_sensitive_reviews(
            container,
            AUTO_REVIEW_ACTOR,
            0,
            skip_on_busy=True,
        )
        logger.info(
            "Startup auto-recheck finished: count=%s summary=%s skipped=%s",
            payload.get("count"),
            payload.get("summary", {}),
            bool(payload.get("skipped")),
        )
        return payload
    except Exception:
        logger.exception("Startup auto-recheck failed")
        return {
            "items": [],
            "summary": {"failed": 1},
            "revision": int(container.store.get_live_rules_state().get("revision") or 0),
            "count": 0,
            "failed": True,
        }


def provider_tuning_changed(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if "provider_profiles" in payload:
        return True
    settings = payload.get("settings")
    if not isinstance(settings, dict):
        return False
    return any(
        key in settings
        for key in (
            "provider_conflict_review_only",
            "provider_mobile_marker_bonus",
            "provider_home_marker_penalty",
        )
    )


def stationary_tuning_changed(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    settings = payload.get("settings")
    if not isinstance(settings, dict):
        return False
    return any(
        key in settings
        for key in (
            "threshold_probable_home",
            "threshold_home",
            "history_lookback_days",
            "history_min_gap_minutes",
            "history_home_same_ip_min_records",
            "history_home_same_ip_min_span_hours",
            "history_home_penalty",
            "lifetime_stationary_hours",
            "score_stationary_penalty",
        )
    )


def detection_recheck_needed(payload: dict[str, Any]) -> bool:
    return provider_tuning_changed(payload) or stationary_tuning_changed(payload)


async def recheck_provider_sensitive_reviews(
    container: Any,
    actor: str,
    actor_tg_id: int,
    *,
    skip_on_busy: bool = False,
) -> dict[str, Any]:
    revision = int(container.store.get_live_rules_state().get("revision") or 0)
    case_ids: list[int] = []
    try:
        for review_reason in ("unsure", "provider_conflict"):
            page = 1
            while True:
                listing = await asyncio.to_thread(
                    container.store.list_review_cases,
                    {
                        "status": "OPEN",
                        "review_reason": review_reason,
                        "page": page,
                        "page_size": 100,
                        "sort": "updated_desc",
                    },
                )
                batch_ids = [int(item["id"]) for item in listing.get("items", [])]
                case_ids.extend(batch_ids)
                if not batch_ids or page * int(listing.get("page_size") or 100) >= int(listing.get("count") or 0):
                    break
                page += 1
    except Exception as exc:
        if skip_on_busy and "database is locked" in str(exc):
            logger.info("Skipping provider-sensitive review recheck because SQLite is busy during listing")
            return _recheck_busy_payload(revision=revision)
        raise
    deduped_case_ids = sorted(set(case_ids))
    return await _recheck_case_ids(
        container,
        deduped_case_ids,
        actor,
        actor_tg_id,
        skip_on_busy=skip_on_busy,
    )


def get_rules(store: Any) -> dict[str, Any]:
    return store.get_live_rules_state()


def update_rules(
    store: Any,
    payload: dict[str, Any],
    actor: str,
    actor_tg_id: int,
    *,
    expected_revision: int | None = None,
    expected_updated_at: str | None = None,
) -> dict[str, Any]:
    try:
        validate_live_rules_patch(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return store.update_live_rules(
            payload,
            actor,
            actor_tg_id,
            expected_revision=expected_revision,
            expected_updated_at=expected_updated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
