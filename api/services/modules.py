from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import secrets
import sqlite3
import textwrap
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from behavioral_analyzers import BehavioralEngine
from mobguard_core.scoring import ScoringContext, ScoringDependencies, evaluate_mobile_network
from mobguard_platform import (
    DecisionBundle,
    ReadSnapshotUnavailableError,
    apply_remote_access_state,
    apply_remote_traffic_cap,
    build_auto_restriction_state,
    review_reason_for_bundle,
    resolve_asn_source,
    should_warning_only,
)
from mobguard_platform.module_secrets import ModuleSecretError, decrypt_module_token, encrypt_module_token
from mobguard_platform.panel_client import PanelClient
from mobguard_platform.runtime import read_env_file, read_env_file_only
from mobguard_platform.runtime_admin_defaults import ENFORCEMENT_SETTINGS_DEFAULTS
from mobguard_platform.storage.sqlite import is_sqlite_busy_error

from ..context import APIContainer
from .limiter_engine import evaluate_limiter_policy_tx


PROTOCOL_VERSION = "v1"
MODULE_TOKEN_PLACEHOLDER = "__PASTE_TOKEN__"
DEFAULT_ACCESS_LOG_PATH = "/var/log/remnanode/access.log"
DEFAULT_STATE_DIR = "./state"
DEFAULT_SPOOL_DIR = "./state/spool"
DEFAULT_MODULE_EVENT_BATCH_SIZE = 25
MODULE_ACTIVITY_WINDOW_SECONDS = 3600


MODULE_INGEST_LOCK = asyncio.Lock()
MODULE_INGEST_BUSY_DETAIL = "Storage is temporarily busy; retry shortly"
HEARTBEAT_DETAIL_CACHE_TTL_SECONDS = 45.0
ACTIVITY_SNAPSHOT_CACHE_TTL_SECONDS = 60.0
_HEARTBEAT_DETAIL_CACHE: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}
_ACTIVITY_SNAPSHOT_CACHE: tuple[float, dict[str, Any]] | None = None


def _container_runtime_dir(container: APIContainer) -> str:
    runtime = getattr(container, "runtime", None)
    runtime_dir = getattr(runtime, "runtime_dir", None)
    if runtime_dir:
        return str(runtime_dir)
    env_path = getattr(runtime, "env_path", None)
    if env_path:
        return str(Path(env_path).parent)
    config_path = getattr(getattr(container, "store", None), "config_path", None)
    if config_path:
        return str(Path(config_path).parent)
    return str(Path("runtime"))


class ModuleIngestionBusyError(RuntimeError):
    pass


class ModuleStorageBusyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModuleBatchContext:
    container: APIContainer
    module: dict[str, Any]
    rules_state: dict[str, Any]
    rules: dict[str, Any]
    settings: dict[str, Any]
    remnawave_client: PanelClient
    ipinfo: Any
    asn_source: Any
    behavior_engine: BehavioralEngine
    exempt_ids: frozenset[int]
    exempt_tg_ids: frozenset[int]


def _ipinfo_client():
    try:
        from ipinfo_api import ipinfo_api
    except ImportError as exc:
        raise RuntimeError(
            "Module ingestion dependencies are missing in mobguard-api image: install aiohttp and rebuild the API image"
        ) from exc
    return ipinfo_api


def _require_protocol_version(protocol_version: str) -> str:
    normalized = str(protocol_version or "").strip() or PROTOCOL_VERSION
    if normalized != PROTOCOL_VERSION:
        raise ValueError(f"Unsupported module protocol version: {normalized}")
    return normalized


def _runtime_settings(container: APIContainer) -> dict[str, Any]:
    return container.store.get_live_rules_state()["rules"].get("settings", {})


def _module_runtime(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "heartbeat_interval_seconds": int(settings.get("module_heartbeat_interval_seconds", 30)),
        "config_poll_interval_seconds": int(settings.get("module_config_poll_interval_seconds", 60)),
        "flush_interval_seconds": int(settings.get("module_flush_interval_seconds", 3)),
        "event_batch_size": int(settings.get("module_event_batch_size", DEFAULT_MODULE_EVENT_BATCH_SIZE)),
        "max_spool_events": int(settings.get("module_max_spool_events", 5000)),
    }


def _module_runtime_settings(container: APIContainer) -> dict[str, Any]:
    runtime_settings: dict[str, Any] = {}
    runtime = getattr(container, "runtime", None)
    runtime_config = getattr(runtime, "config", None)
    if isinstance(runtime_config, dict):
        candidate = runtime_config.get("settings")
        if isinstance(candidate, dict):
            runtime_settings = dict(candidate)
    live_settings = _runtime_settings(container)
    return {**runtime_settings, **live_settings}


def _module_stale_after_seconds(container: APIContainer) -> int:
    heartbeat_interval_seconds = max(
        int(_module_runtime(_module_runtime_settings(container))["heartbeat_interval_seconds"]),
        1,
    )
    return max(heartbeat_interval_seconds * 4, 180)


def _apply_module_freshness(module: dict[str, Any], *, stale_after_seconds: int) -> dict[str, Any]:
    payload = dict(module)
    last_seen_raw = str(payload.get("last_seen_at") or "").strip()
    last_seen = datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
    seconds_since_last_seen: int | None = None
    if last_seen:
        seconds_since_last_seen = max(int((datetime.utcnow().replace(microsecond=0) - last_seen).total_seconds()), 0)
    payload["stale_after_seconds"] = int(stale_after_seconds)
    payload["seconds_since_last_seen"] = seconds_since_last_seen
    payload["healthy"] = bool(seconds_since_last_seen is not None and seconds_since_last_seen <= stale_after_seconds)
    return payload


def _remnawave_client(container: APIContainer) -> PanelClient:
    runtime_settings = {}
    runtime = getattr(container, "runtime", None)
    runtime_config = getattr(runtime, "config", None)
    if isinstance(runtime_config, dict):
        runtime_settings = runtime_config.get("settings", {}) if isinstance(runtime_config.get("settings", {}), dict) else {}
    settings = _runtime_settings(container)
    env_path = getattr(runtime, "env_path", None)
    env_values = read_env_file(str(env_path)) if env_path else {}
    base_url = str(
        runtime_settings.get("remnawave_api_url")
        or runtime_settings.get("panel_url")
        or settings.get("remnawave_api_url")
        or settings.get("panel_url")
        or ""
    ).strip()
    token = (
        os.getenv("REMNAWAVE_API_TOKEN")
        or env_values.get("REMNAWAVE_API_TOKEN")
        or os.getenv("PANEL_TOKEN")
        or env_values.get("PANEL_TOKEN")
        or ""
    )
    signature = (base_url.rstrip("/"), str(token or ""))
    cached = getattr(container, "_panel_client_cache", None)
    cached_signature = getattr(container, "_panel_client_signature", None)
    if isinstance(cached, PanelClient) and cached_signature == signature:
        return cached
    client = PanelClient(base_url, token)
    setattr(container, "_panel_client_cache", client)
    setattr(container, "_panel_client_signature", signature)
    return client


def _module_secret_key(container: APIContainer) -> str:
    env_values = read_env_file_only(str(container.runtime.env_path))
    secret_key = str(env_values.get("MOBGUARD_MODULE_SECRET_KEY") or "").strip()
    if not secret_key:
        raise ValueError("MOBGUARD_MODULE_SECRET_KEY is not configured")
    return secret_key


def _normalize_api_base_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if not normalized:
        return ""
    return normalized if normalized.endswith("/api") else f"{normalized}/api"


def _panel_base_url(container: APIContainer) -> str:
    runtime_settings = {}
    runtime_config = getattr(container.runtime, "config", None)
    if isinstance(runtime_config, dict):
        runtime_settings = runtime_config.get("settings", {}) if isinstance(runtime_config.get("settings", {}), dict) else {}
    settings = _runtime_settings(container)
    public_ui_base = str(
        runtime_settings.get("review_ui_base_url")
        or settings.get("review_ui_base_url")
        or ""
    ).strip()
    if public_ui_base:
        return _normalize_api_base_url(public_ui_base)
    fallback_base = str(
        runtime_settings.get("panel_url")
        or settings.get("panel_url")
        or runtime_settings.get("remnawave_api_url")
        or settings.get("remnawave_api_url")
        or ""
    ).strip()
    return _normalize_api_base_url(fallback_base) or "__SET_PANEL_BASE_URL__/api"


def _yaml_string(value: Any) -> str:
    return '"' + str(value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalize_inbound_tags(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("inbound_tags must be a list")
    return [str(item or "").strip() for item in values if str(item or "").strip()]


def _module_metadata_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    module_name = str(payload.get("module_name") or "").strip()
    if not module_name:
        raise ValueError("module_name is required")
    return {
        "module_name": module_name,
        "metadata": {
            "inbound_tags": _normalize_inbound_tags(payload.get("inbound_tags") or []),
        },
    }


def _module_install_payload(container: APIContainer, module: dict[str, Any]) -> dict[str, Any]:
    inbound_tags = module.get("inbound_tags") or []
    log_mount = f"{DEFAULT_ACCESS_LOG_PATH}:{DEFAULT_ACCESS_LOG_PATH}:ro"
    compose_yaml = textwrap.dedent(
        f"""\
        # MobGuard module install bundle
        # Module: {module.get("module_name") or module.get("module_id")}
        # INBOUND tags: {", ".join(inbound_tags) if inbound_tags else "n/a"}
        # Copy the token from the panel and replace {MODULE_TOKEN_PLACEHOLDER} before start.
        # If your node uses a different access log path, edit ACCESS_LOG_PATH locally before start.
        services:
          mobguard-module:
            build:
              context: .
              dockerfile: Dockerfile
            container_name: {module.get("module_id") or "mobguard-module"}
            restart: unless-stopped
            environment:
              PANEL_BASE_URL: {_yaml_string(_panel_base_url(container))}
              MODULE_ID: {_yaml_string(module.get("module_id") or "")}
              MODULE_TOKEN: {_yaml_string(MODULE_TOKEN_PLACEHOLDER)}
              ACCESS_LOG_PATH: {_yaml_string(DEFAULT_ACCESS_LOG_PATH)}
              STATE_DIR: {_yaml_string(DEFAULT_STATE_DIR)}
              SPOOL_DIR: {_yaml_string(DEFAULT_SPOOL_DIR)}
            volumes:
              - ./state:/app/state
              - {_yaml_string(log_mount)}
        """
    ).strip()
    return {"compose_yaml": compose_yaml}


def _module_detail_response(container: APIContainer, module: dict[str, Any]) -> dict[str, Any]:
    return {"module": module, "install": _module_install_payload(container, module)}


def _generate_module_id(container: APIContainer) -> str:
    for _ in range(10):
        candidate = f"module-{uuid.uuid4().hex[:12]}"
        if not container.store.get_module(candidate):
            return candidate
    raise ValueError("Failed to generate a unique module_id")


def _event_uid(module_id: str, payload: dict[str, Any]) -> str:
    raw_uid = str(payload.get("event_uid") or "").strip()
    if raw_uid:
        return raw_uid
    fallback = "|".join(
        [
            str(module_id),
            str(payload.get("log_offset") or ""),
            str(payload.get("occurred_at") or ""),
            str(payload.get("uuid") or ""),
            str(payload.get("system_id") or ""),
            str(payload.get("telegram_id") or ""),
            str(payload.get("ip") or ""),
            str(payload.get("tag") or ""),
        ]
    )
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _heartbeat_detail_map(container: APIContainer, module_ids: list[str]) -> dict[str, dict[str, Any]]:
    global _HEARTBEAT_DETAIL_CACHE
    if not module_ids:
        return {}
    normalized_module_ids = tuple(sorted(set(module_ids)))
    cache_key = "|".join(normalized_module_ids)
    cached = _HEARTBEAT_DETAIL_CACHE.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return copy.deepcopy(cached[1])
    placeholders = ", ".join("?" for _ in normalized_module_ids)
    query = f"""
        SELECT module_id, details_json
        FROM (
            SELECT
                mh.module_id,
                mh.details_json,
                ROW_NUMBER() OVER (
                    PARTITION BY mh.module_id
                    ORDER BY mh.created_at DESC, mh.id DESC
                ) AS rn
            FROM module_heartbeats mh
            WHERE mh.module_id IN ({placeholders})
        ) ranked
        WHERE rn = 1
    """
    try:
        with container.store._snapshot_connect(fast_read=True) as conn:
            rows = conn.execute(query, list(normalized_module_ids)).fetchall()
    except sqlite3.OperationalError:
        return copy.deepcopy(cached[1]) if cached else {}
    payload: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_details = str(row["details_json"] or "").strip() or "{}"
        try:
            details = json.loads(raw_details)
        except json.JSONDecodeError:
            details = {}
        if isinstance(details, dict):
            payload[str(row["module_id"] or "").strip()] = details
    _HEARTBEAT_DETAIL_CACHE[cache_key] = (
        time.monotonic() + HEARTBEAT_DETAIL_CACHE_TTL_SECONDS,
        copy.deepcopy(payload),
    )
    return payload


def _activity_identity_sql() -> str:
    return """
        COALESCE(
            NULLIF(subject_uuid, ''),
            CASE WHEN system_id IS NOT NULL THEN 'sys:' || CAST(system_id AS TEXT) END,
            CASE WHEN telegram_id IS NOT NULL AND telegram_id != '' THEN 'tg:' || telegram_id END,
            CASE WHEN username IS NOT NULL AND username != '' THEN 'usr:' || username END,
            'ip:' || ip
        )
    """


def _activity_snapshot(
    container: APIContainer,
    *,
    window_seconds: int = MODULE_ACTIVITY_WINDOW_SECONDS,
) -> dict[str, Any]:
    global _ACTIVITY_SNAPSHOT_CACHE
    cached = _ACTIVITY_SNAPSHOT_CACHE
    if cached and cached[0] > time.monotonic():
        return copy.deepcopy(cached[1])
    created_from = (
        datetime.utcnow().replace(microsecond=0) - timedelta(seconds=max(int(window_seconds), 60))
    ).isoformat()
    identity_sql = """
        COALESCE(
            NULLIF(subject_key, ''),
            NULLIF(uuid, ''),
            CASE WHEN system_id IS NOT NULL THEN 'sys:' || CAST(system_id AS TEXT) END,
            CASE WHEN telegram_id IS NOT NULL AND telegram_id != '' THEN 'tg:' || telegram_id END,
            CASE WHEN username IS NOT NULL AND username != '' THEN 'usr:' || username END,
            'ip:' || ip
        )
    """
    try:
        with container.store._snapshot_connect(fast_read=True) as conn:
            event_rows = conn.execute(
                f"""
                SELECT
                    module_id,
                    COUNT(*) AS recent_events,
                    COUNT(DISTINCT {identity_sql}) AS recent_active_users
                FROM analysis_events
                WHERE created_at >= ?
                GROUP BY module_id
                """,
                (created_from,),
            ).fetchall()
            total_row = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS recent_events_total,
                    COUNT(DISTINCT {identity_sql}) AS recent_active_users_total
                FROM analysis_events
                WHERE created_at >= ?
                """,
                (created_from,),
            ).fetchone()
            has_active_trackers = container.store._table_exists(conn, "active_trackers")
            module_activity_rows = conn.execute(
                """
                WITH active_tracker_keys AS (
                    SELECT DISTINCT
                        SUBSTR(key, 1, INSTR(key, ':') - 1) AS uuid,
                        SUBSTR(key, INSTR(key, ':') + 1) AS ip
                    FROM active_trackers
                    WHERE INSTR(key, ':') > 0 AND last_seen >= ?
                ),
                ranked_events AS (
                    SELECT
                        atk.uuid,
                        atk.ip,
                        ae.module_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY atk.uuid, atk.ip
                            ORDER BY ae.created_at DESC, ae.id DESC
                        ) AS rn
                    FROM active_tracker_keys atk
                    INNER JOIN analysis_events ae
                        ON ae.uuid = atk.uuid
                       AND ae.ip = atk.ip
                    WHERE ae.module_id IS NOT NULL AND ae.module_id != ''
                )
                SELECT module_id, COUNT(*) AS active_users
                FROM ranked_events
                WHERE rn = 1
                GROUP BY module_id
                """,
                (created_from,),
            ).fetchall() if has_active_trackers else []
            active_total_row = conn.execute(
                """
                SELECT COUNT(*) AS active_users_total
                FROM (
                    SELECT DISTINCT SUBSTR(key, 1, INSTR(key, ':') - 1) AS uuid
                    FROM active_trackers
                    WHERE INSTR(key, ':') > 0 AND last_seen >= ?
                )
                """,
                (created_from,),
            ).fetchone() if has_active_trackers else None
    except sqlite3.OperationalError:
        if cached:
            return copy.deepcopy(cached[1])
        payload = {
            "window_seconds": int(window_seconds),
            "modules": {},
            "totals": {
                "recent_events_total": 0,
                "active_users_total": 0,
            },
        }
        _ACTIVITY_SNAPSHOT_CACHE = (
            time.monotonic() + ACTIVITY_SNAPSHOT_CACHE_TTL_SECONDS,
            copy.deepcopy(payload),
        )
        return payload
    payload = {
        "window_seconds": int(window_seconds),
        "modules": {},
        "totals": {
            "recent_events_total": int(total_row["recent_events_total"] or 0) if total_row else 0,
            "active_users_total": 0,
        },
    }
    tracker_active_total = int(active_total_row["active_users_total"] or 0) if active_total_row else 0
    recent_active_total = int(total_row["recent_active_users_total"] or 0) if total_row else 0
    payload["totals"]["active_users_total"] = (
        tracker_active_total if tracker_active_total > 0 else recent_active_total
    )
    for row in event_rows:
        module_id = str(row["module_id"] or "").strip()
        if not module_id:
            continue
        payload["modules"][module_id] = {
            "recent_events": int(row["recent_events"] or 0),
            "active_users": int(row["recent_active_users"] or 0) if not module_activity_rows else 0,
        }
    for row in module_activity_rows:
        module_id = str(row["module_id"] or "").strip()
        if not module_id:
            continue
        module_payload = payload["modules"].setdefault(
            module_id,
            {
                "recent_events": 0,
                "active_users": 0,
            },
        )
        module_payload["active_users"] = int(row["active_users"] or 0)
    _ACTIVITY_SNAPSHOT_CACHE = (
        time.monotonic() + ACTIVITY_SNAPSHOT_CACHE_TTL_SECONDS,
        copy.deepcopy(payload),
    )
    return payload


def _normalize_runtime_metrics(
    details: dict[str, Any],
    *,
    activity_window_seconds: int,
    active_users: int,
    recent_events: int,
) -> dict[str, Any]:
    system_raw = details.get("system") if isinstance(details.get("system"), dict) else {}
    processes_raw = details.get("processes") if isinstance(details.get("processes"), dict) else {}
    top_raw = processes_raw.get("top") if isinstance(processes_raw.get("top"), list) else []
    system = {
        "cpu_percent": _coerce_float(system_raw.get("cpu_percent")),
        "cpu_cores": _coerce_int(system_raw.get("cpu_cores")),
        "load_avg_1m": _coerce_float(system_raw.get("load_avg_1m")),
        "load_avg_5m": _coerce_float(system_raw.get("load_avg_5m")),
        "load_avg_15m": _coerce_float(system_raw.get("load_avg_15m")),
        "memory_total_bytes": _coerce_int(system_raw.get("memory_total_bytes")),
        "memory_used_bytes": _coerce_int(system_raw.get("memory_used_bytes")),
        "memory_percent": _coerce_float(system_raw.get("memory_percent")),
        "disk_total_bytes": _coerce_int(system_raw.get("disk_total_bytes")),
        "disk_used_bytes": _coerce_int(system_raw.get("disk_used_bytes")),
        "disk_percent": _coerce_float(system_raw.get("disk_percent")),
        "disk_read_bps": _coerce_int(system_raw.get("disk_read_bps")),
        "disk_write_bps": _coerce_int(system_raw.get("disk_write_bps")),
        "uptime_seconds": _coerce_int(system_raw.get("uptime_seconds")),
    }
    processes = {
        "match_count": _coerce_int(processes_raw.get("match_count")) or 0,
        "cpu_percent": _coerce_float(processes_raw.get("cpu_percent")),
        "rss_bytes": _coerce_int(processes_raw.get("rss_bytes")),
        "vms_bytes": _coerce_int(processes_raw.get("vms_bytes")),
        "top": [
            {
                "pid": _coerce_int(item.get("pid")),
                "name": str(item.get("name") or "").strip(),
                "cmdline": str(item.get("cmdline") or "").strip(),
                "cpu_percent": _coerce_float(item.get("cpu_percent")),
                "rss_bytes": _coerce_int(item.get("rss_bytes")),
                "vms_bytes": _coerce_int(item.get("vms_bytes")),
            }
            for item in top_raw
            if isinstance(item, dict)
        ],
    }
    return {
        "activity_window_seconds": int(activity_window_seconds),
        "active_users": int(active_users),
        "recent_events": int(recent_events),
        "system": system,
        "processes": processes,
        "collected_at": str(details.get("collected_at") or "").strip() or None,
    }


def _attach_runtime_metrics(
    container: APIContainer,
    modules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    module_ids = [str(item.get("module_id") or "").strip() for item in modules if str(item.get("module_id") or "").strip()]
    heartbeat_details = _heartbeat_detail_map(container, module_ids)
    activity = _activity_snapshot(container)
    per_module_activity = activity.get("modules", {})
    activity_window_seconds = int(activity.get("window_seconds") or MODULE_ACTIVITY_WINDOW_SECONDS)
    enriched: list[dict[str, Any]] = []
    healthy_count = 0
    warning_count = 0
    error_count = 0
    stale_count = 0
    pending_count = 0
    cpu_values: list[float] = []
    memory_total_bytes = 0
    memory_used_bytes = 0
    disk_total_bytes = 0
    disk_used_bytes = 0
    mobguard_process_cpu_percent = 0.0
    mobguard_process_rss_bytes = 0

    for module in modules:
        payload = dict(module)
        module_id = str(payload.get("module_id") or "").strip()
        module_activity = per_module_activity.get(module_id, {})
        details = heartbeat_details.get(module_id, {})
        payload["runtime_metrics"] = _normalize_runtime_metrics(
            details,
            activity_window_seconds=activity_window_seconds,
            active_users=int(module_activity.get("active_users") or 0),
            recent_events=int(module_activity.get("recent_events") or 0),
        )
        enriched.append(payload)

        if payload.get("install_state") == "pending_install":
            pending_count += 1
        elif not payload.get("healthy"):
            stale_count += 1
        elif payload.get("health_status") == "error":
            error_count += 1
        elif payload.get("health_status") == "warn":
            warning_count += 1
        else:
            healthy_count += 1

        system = payload["runtime_metrics"]["system"]
        processes = payload["runtime_metrics"]["processes"]
        cpu_percent = system.get("cpu_percent")
        if cpu_percent is not None:
            cpu_values.append(float(cpu_percent))
        memory_total_bytes += int(system.get("memory_total_bytes") or 0)
        memory_used_bytes += int(system.get("memory_used_bytes") or 0)
        disk_total_bytes += int(system.get("disk_total_bytes") or 0)
        disk_used_bytes += int(system.get("disk_used_bytes") or 0)
        mobguard_process_cpu_percent += float(processes.get("cpu_percent") or 0.0)
        mobguard_process_rss_bytes += int(processes.get("rss_bytes") or 0)

    return enriched, {
        "activity_window_seconds": activity_window_seconds,
        "total_modules": len(enriched),
        "pending_modules": pending_count,
        "healthy_modules": healthy_count,
        "warning_modules": warning_count,
        "error_modules": error_count,
        "stale_modules": stale_count,
        "modules_with_metrics": sum(1 for item in enriched if item.get("runtime_metrics", {}).get("collected_at")),
        "active_users_total": int(activity.get("totals", {}).get("active_users_total") or 0),
        "recent_events_total": int(activity.get("totals", {}).get("recent_events_total") or 0),
        "avg_cpu_percent": round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else None,
        "peak_cpu_percent": round(max(cpu_values), 1) if cpu_values else None,
        "memory_total_bytes": memory_total_bytes,
        "memory_used_bytes": memory_used_bytes,
        "disk_total_bytes": disk_total_bytes,
        "disk_used_bytes": disk_used_bytes,
        "mobguard_process_cpu_percent": round(mobguard_process_cpu_percent, 1),
        "mobguard_process_rss_bytes": mobguard_process_rss_bytes,
    }


async def _resolve_remote_user(
    runtime: ModuleBatchContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    identifier = next(
        (
            value
            for value in (
                payload.get("uuid"),
                payload.get("system_id"),
                payload.get("telegram_id"),
                payload.get("username"),
            )
            if value not in (None, "")
        ),
        None,
    )
    remote_user = {}
    client = runtime.remnawave_client
    if identifier not in (None, "") and client.enabled:
        remote_user = await asyncio.to_thread(client.get_user_data, str(identifier).strip()) or {}
    user_data = dict(remote_user)
    if payload.get("uuid") and not user_data.get("uuid"):
        user_data["uuid"] = payload["uuid"]
    if payload.get("username") and not user_data.get("username"):
        user_data["username"] = payload["username"]
    if payload.get("system_id") not in (None, "") and user_data.get("id") is None:
        user_data["id"] = int(payload["system_id"])
    if payload.get("telegram_id") not in (None, "") and user_data.get("telegramId") is None:
        user_data["telegramId"] = str(payload["telegram_id"])
    return user_data


async def _analyze_event(
    runtime: ModuleBatchContext,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    *,
    persist_behavior_state: bool = True,
    persist_decision: bool = True,
) -> DecisionBundle:
    container = runtime.container
    ipinfo = runtime.ipinfo

    async def get_manual_override(target_ip: str) -> Optional[str]:
        manual_decision = await container.store.async_get_ip_override(target_ip)
        if manual_decision:
            return manual_decision
        return await container.analysis_store.get_unsure_pattern(target_ip)

    async def analyze_behavior(current_uuid: str, target_ip: str, current_tag: str) -> dict[str, Any]:
        result = await runtime.behavior_engine.analyze(
            current_uuid,
            target_ip,
            current_tag,
            persist_state=persist_behavior_state,
        )
        result["subnet"] = container.analysis_store.get_subnet(target_ip)
        return result

    async def record_decision(ip: str, uuid: str, verdict: str) -> None:
        if persist_decision:
            await runtime.behavior_engine.record_decision(ip, uuid, verdict)

    def record_stats(asn: Optional[int], status: str, matched_kw: Optional[str], org: str) -> None:
        # Daily/stat buffers are not part of the panel control-plane contract in v1.
        return None

    def resolve_asn(target_ip: str) -> tuple[Optional[int], str, str]:
        asn, provider = runtime.asn_source.lookup(target_ip)
        source_type = str(getattr(runtime.asn_source, "source_type", "unknown") or "unknown")
        provider_known = str(provider or "").strip().lower() not in {"", "unknown", "unknown isp"}
        return asn, provider, source_type if asn is not None or provider_known else "unknown"

    bundle = await evaluate_mobile_network(
        context=ScoringContext(
            ip=str(payload["ip"]),
            uuid=str(user_data.get("uuid") or "") or None,
            tag=str(payload.get("tag") or "") or None,
        ),
        config=runtime.rules,
        deps=ScoringDependencies(
            get_manual_override=get_manual_override,
            get_ip_info=ipinfo.get_ip_info,
            parse_asn=ipinfo.parse_asn,
            resolve_asn=resolve_asn,
            normalize_isp_name=ipinfo.normalize_isp_name,
            is_datacenter=ipinfo.is_datacenter,
            analyze_behavior=analyze_behavior,
            get_promoted_pattern=container.store.async_get_promoted_pattern,
            get_legacy_confidence=container.analysis_store.get_learning_confidence,
            check_ip_api_mobile=lambda _: asyncio.sleep(0, result=None),
            record_decision=record_decision,
            record_stats=record_stats,
        ),
    )
    return bundle


async def _apply_enforcement_if_needed(
    runtime: ModuleBatchContext,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    bundle: DecisionBundle,
) -> Optional[dict[str, Any]]:
    container = runtime.container
    client = runtime.remnawave_client
    settings = runtime.settings
    if bundle.verdict != "HOME" or bundle.confidence_band not in {"HIGH_HOME", "PROBABLE_HOME"}:
        return None
    uuid = str(user_data.get("uuid") or "").strip()
    if not uuid:
        return None

    def _evaluate_limiter() -> dict[str, Any]:
        with container.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            decision = evaluate_limiter_policy_tx(
                conn,
                settings,
                user_data,
                payload,
                bundle,
                action="enforcement",
            )
            conn.commit()
            return decision.to_dict()

    limiter = await asyncio.to_thread(_evaluate_limiter)
    limiter_payload = limiter if str(limiter.get("reason") or "") != "disabled" else None
    limiter_reason = str(limiter.get("reason") or "")
    if not bool(limiter.get("allowed")):
        if limiter_reason == "rollout_warning_only":
            warning_only_from_limiter = True
        elif limiter_reason in {"below_threshold", "cooldown_active", "ignore_ttl", "rollout_observe"}:
            return {
                "type": "suppressed",
                "reason": limiter_reason,
                "warning_only": False,
                "delivery_status": "suppressed",
                "dry_run": bool(settings.get("dry_run", True)),
                **({"limiter": limiter_payload} if limiter_payload else {}),
            }
        else:
            warning_only_from_limiter = False
    else:
        warning_only_from_limiter = False

    warning_only = (
        warning_only_from_limiter
        or bool(settings.get("warning_only_mode", False))
        or bool(settings.get("shadow_mode", True))
        or should_warning_only(bundle)
        or not bundle.punitive_eligible
    )
    observe_only = bool(settings.get("dry_run", True)) or not client.enabled
    now = datetime.utcnow().replace(microsecond=0)
    row = await container.analysis_store.fetch_one(
        """
        SELECT strikes, warning_count
        FROM violations
        WHERE uuid = ?
        """,
        (uuid,),
    )
    strikes = int(row["strikes"]) if row and row["strikes"] is not None else 0
    warning_count = int(row["warning_count"]) if row and row["warning_count"] is not None else 0

    if warning_only:
        next_warning_count = warning_count + 1
        if observe_only:
            return {
                "type": "warning",
                "warning_count": next_warning_count,
                "warning_only": True,
                "dry_run": True,
                **({"limiter": limiter_payload} if limiter_payload else {}),
            }
        await container.analysis_store.execute(
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
                now.isoformat(),
                now.isoformat(),
                now.isoformat(),
                next_warning_count,
            ),
        )
        return {
            "type": "warning",
            "warning_count": next_warning_count,
            "warning_only": True,
            **({"limiter": limiter_payload} if limiter_payload else {}),
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
    if observe_only:
        return {
            "type": "ban",
            "strike": next_strike,
            "ban_minutes": duration,
            "remote_updated": False,
            "dry_run": True,
            **({"limiter": limiter_payload} if limiter_payload else {}),
        }
    unban_time = now + timedelta(minutes=duration)
    await container.analysis_store.execute(
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
            unban_time.isoformat(),
            now.isoformat(),
            now.isoformat(),
            restriction_state["restriction_mode"],
            restriction_state["saved_traffic_limit_bytes"],
            restriction_state["saved_traffic_limit_strategy"],
            restriction_state["applied_traffic_limit_bytes"],
        ),
    )
    await container.analysis_store.execute(
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
            now.isoformat(),
        ),
    )
    def _remote_apply() -> bool:
        if restriction_state["restriction_mode"] == "TRAFFIC_CAP":
            result = apply_remote_traffic_cap(
                client,
                uuid,
                user_data,
                int(settings.get("traffic_cap_increment_gb", ENFORCEMENT_SETTINGS_DEFAULTS["traffic_cap_increment_gb"])),
            )
            return bool(result["remote_updated"])
        return apply_remote_access_state(client, uuid, settings, restricted=True)

    remote_updated = await asyncio.to_thread(_remote_apply)
    return {
        "type": "ban",
        "strike": next_strike,
        "ban_minutes": duration,
        "remote_updated": bool(remote_updated),
        "dry_run": False,
        **({"limiter": limiter_payload} if limiter_payload else {}),
    }


async def _process_module_event(
    runtime: ModuleBatchContext,
    _module: dict[str, Any] | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    container = runtime.container
    module = _module or runtime.module
    raw_ip = str(payload.get("ip") or "").strip()
    if not raw_ip:
        raise ValueError("Raw event is missing ip")

    user_data = await _resolve_remote_user(runtime, payload)
    user_data["module_id"] = module["module_id"]
    user_data["module_name"] = module["module_name"]

    system_id = user_data.get("id")
    telegram_id = user_data.get("telegramId")
    if system_id is not None and int(system_id) in runtime.exempt_ids:
        return {"status": "skipped", "reason": "exempt_system_id"}
    if telegram_id not in (None, "") and int(telegram_id) in runtime.exempt_tg_ids:
        return {"status": "skipped", "reason": "exempt_telegram_id"}

    manual_override = await container.store.async_get_ip_override(raw_ip)
    cached = None
    if not manual_override:
        manual_override = await container.analysis_store.get_unsure_pattern(raw_ip)
    if not manual_override:
        cached = await container.analysis_store.get_cached_decision(raw_ip)

    if cached:
        bundle = DecisionBundle.from_cache_record(raw_ip, cached)
    else:
        bundle = await _analyze_event(runtime, user_data, payload)
        await container.analysis_store.cache_decision(raw_ip, bundle.to_cache_payload())
    uuid_value = str(user_data.get("uuid") or "").strip()
    if uuid_value:
        await container.analysis_store.update_ip_history(uuid_value, raw_ip)
        await container.analysis_store.update_session(
            uuid_value,
            raw_ip,
            str(payload.get("tag") or ""),
        )
        if bundle.verdict in {"MOBILE", "HOME"}:
            await container.analysis_store.record_subnet_signal(raw_ip, uuid_value, bundle.verdict)

    event_id = await container.store.async_record_analysis_event(
        user_data,
        raw_ip,
        str(payload.get("tag") or ""),
        bundle,
        {
            "client_device_id": payload.get("client_device_id"),
            "client_device_label": payload.get("client_device_label"),
            "client_os_family": payload.get("client_os_family"),
            "client_os_version": payload.get("client_os_version"),
            "client_app_name": payload.get("client_app_name"),
            "client_app_version": payload.get("client_app_version"),
        },
    )
    bundle.event_id = event_id

    review_case_id: Optional[int] = None
    review_reason = review_reason_for_bundle(bundle)
    if review_reason:
        review_case = await container.store.async_ensure_review_case(
            user_data,
            raw_ip,
            str(payload.get("tag") or ""),
            bundle,
            event_id,
            review_reason,
        )
        review_case_id = review_case.id
        bundle.case_id = review_case_id

    enforcement_result = await _apply_enforcement_if_needed(
        runtime,
        user_data,
        payload,
        bundle,
    )
    return {
        "status": "processed",
        "event_id": event_id,
        "review_case_id": review_case_id,
        "bundle": bundle.to_dict(),
        "review_reason": review_reason,
        "enforcement": enforcement_result,
    }


def _build_batch_context(container: APIContainer, module: dict[str, Any]) -> ModuleBatchContext:
    rules_state = container.store.get_live_rules_state()
    rules = rules_state["rules"]
    settings = rules.get("settings", {})
    return ModuleBatchContext(
        container=container,
        module=module,
        rules_state=rules_state,
        rules=rules,
        settings=settings,
        remnawave_client=_remnawave_client(container),
        ipinfo=_ipinfo_client(),
        asn_source=resolve_asn_source(
            _container_runtime_dir(container),
            settings.get("geoip_db") or container.store.base_config.get("settings", {}).get("geoip_db"),
        ),
        behavior_engine=BehavioralEngine(container.analysis_store, rules),
        exempt_ids=frozenset(int(value) for value in rules.get("exempt_ids", [])),
        exempt_tg_ids=frozenset(int(value) for value in rules.get("exempt_tg_ids", [])),
    )


def register_module(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    metadata_payload = payload.get("metadata")
    try:
        module = container.store.register_module(
            str(payload.get("module_id") or ""),
            token,
            module_name=str(payload.get("module_name") or ""),
            version=str(payload.get("version") or ""),
            protocol_version=protocol_version,
            metadata=dict(metadata_payload) if isinstance(metadata_payload, dict) else None,
            config_revision_applied=int(payload.get("config_revision_applied") or 0),
            auto_create=False,
        )
    except sqlite3.OperationalError as exc:
        if not is_sqlite_busy_error(exc):
            raise
        raise ModuleStorageBusyError(MODULE_INGEST_BUSY_DETAIL) from exc
    stale_after_seconds = _module_stale_after_seconds(container)
    return {
        "protocol_version": protocol_version,
        "module": _apply_module_freshness(module, stale_after_seconds=stale_after_seconds),
        "config": get_module_config(container, module)["config"],
    }


def record_module_heartbeat(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    try:
        module = container.store.authenticate_module(str(payload.get("module_id") or ""), token)
        updated = container.store.record_module_heartbeat(
            module["module_id"],
            status=str(payload.get("status") or "online"),
            version=str(payload.get("version") or module.get("version") or ""),
            protocol_version=protocol_version,
            config_revision_applied=int(payload.get("config_revision_applied") or 0),
            details=dict(payload.get("details") or {}),
        )
    except sqlite3.OperationalError as exc:
        if not is_sqlite_busy_error(exc):
            raise
        raise ModuleStorageBusyError(MODULE_INGEST_BUSY_DETAIL) from exc
    stale_after_seconds = _module_stale_after_seconds(container)
    return {
        "protocol_version": protocol_version,
        "module": _apply_module_freshness(updated, stale_after_seconds=stale_after_seconds),
        "desired_config_revision": container.store.get_live_rules_state()["revision"],
    }


def get_module_config(container: APIContainer, module: dict[str, Any] | None) -> dict[str, Any]:
    rules_state = container.store.get_live_rules_state()
    settings = _module_runtime_settings(container)
    rules = copy.deepcopy(rules_state["rules"])
    inbound_tags = list((module or {}).get("inbound_tags") or [])
    rules["inbound_tags"] = inbound_tags
    rules["mobile_tags"] = list(inbound_tags)
    return {
        "config": {
            "protocol_version": PROTOCOL_VERSION,
            "config_revision": rules_state["revision"],
            "updated_at": rules_state["updated_at"],
            "rules": rules,
            "module_runtime": _module_runtime(settings),
        },
        "module": module,
    }


async def ingest_module_events(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    try:
        module = container.store.authenticate_module(str(payload.get("module_id") or ""), token)
    except sqlite3.OperationalError as exc:
        if not is_sqlite_busy_error(exc):
            raise
        raise ModuleStorageBusyError(MODULE_INGEST_BUSY_DETAIL) from exc
    try:
        items = []
        for raw_item in list(payload.get("items") or []):
            item = dict(raw_item)
            uid = _event_uid(module["module_id"], item)
            items.append({**item, "event_uid": uid})
        enqueue_result = await asyncio.to_thread(
            container.store.enqueue_raw_events,
            module["module_id"],
            module["module_name"],
            items,
        )
    except sqlite3.OperationalError as exc:
        if not is_sqlite_busy_error(exc):
            raise
        raise ModuleStorageBusyError(MODULE_INGEST_BUSY_DETAIL) from exc

    return {
        "protocol_version": protocol_version,
        "module_id": module["module_id"],
        "accepted": int(enqueue_result.get("accepted") or 0),
        "duplicates": int(enqueue_result.get("duplicates") or 0),
        "queued": int(enqueue_result.get("queued") or 0),
        "config_revision": int(container.store.get_live_rules_state()["revision"] or 0),
        "status": "queued",
    }


def list_modules(container: APIContainer) -> dict[str, Any]:
    stale_after_seconds = _module_stale_after_seconds(container)
    try:
        modules = container.store.list_modules(
            stale_after_seconds=stale_after_seconds,
            include_counters=False,
            fast_read=True,
        )
        fresh_modules = [
            _apply_module_freshness(module, stale_after_seconds=stale_after_seconds)
            for module in modules
        ]
        enriched_items, summary = _attach_runtime_metrics(container, fresh_modules)
        return {
            "items": enriched_items,
            "count": len(enriched_items),
            "summary": summary,
            "pipeline": container.store.get_ingest_pipeline_status(fast_read=True),
        }
    except ReadSnapshotUnavailableError as exc:
        raise ValueError(f"Module list is temporarily unavailable ({exc.reason})") from exc


def create_managed_module(container: APIContainer, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _module_metadata_from_payload(payload)
    try:
        token = secrets.token_urlsafe(32)
        token_ciphertext = encrypt_module_token(_module_secret_key(container), token)
    except ModuleSecretError as exc:
        raise ValueError(str(exc)) from exc
    module = container.store.create_managed_module(
        _generate_module_id(container),
        token,
        token_ciphertext,
        module_name=normalized["module_name"],
        protocol_version=PROTOCOL_VERSION,
        metadata=normalized["metadata"],
    )
    stale_after_seconds = _module_stale_after_seconds(container)
    return {
        "module": _apply_module_freshness(module, stale_after_seconds=stale_after_seconds),
        "install": {
            **_module_install_payload(container, module),
            "module_token": token,
        },
    }


def get_module_detail(container: APIContainer, module_id: str) -> dict[str, Any]:
    module = container.store.get_module(module_id)
    if not module:
        raise ValueError("Module is not registered")
    enriched_modules, _ = _attach_runtime_metrics(
        container,
        [_apply_module_freshness(module, stale_after_seconds=_module_stale_after_seconds(container))],
    )
    return _module_detail_response(
        container,
        enriched_modules[0],
    )


def update_module_detail(container: APIContainer, module_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _module_metadata_from_payload(payload)
    module = container.store.update_managed_module(
        module_id,
        module_name=normalized["module_name"],
        metadata=normalized["metadata"],
    )
    enriched_modules, _ = _attach_runtime_metrics(
        container,
        [_apply_module_freshness(module, stale_after_seconds=_module_stale_after_seconds(container))],
    )
    return _module_detail_response(
        container,
        enriched_modules[0],
    )


def reveal_module_token(container: APIContainer, module_id: str) -> dict[str, Any]:
    try:
        token = decrypt_module_token(
            _module_secret_key(container),
            container.store.get_module_token_ciphertext(module_id),
        )
    except ModuleSecretError as exc:
        raise ValueError(str(exc)) from exc
    return {"module_id": module_id, "module_token": token}
