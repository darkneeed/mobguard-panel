from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException

from mobguard_platform.runtime import (
    env_field_payload,
    normalize_runtime_bound_settings,
    read_env_file,
    read_json_file,
    update_json_file,
)
from mobguard_platform.panel_client import PanelClient
from mobguard_platform.review_context import subject_key_from_identity
from mobguard_platform.usage_profile import build_usage_profile_snapshot
from mobguard_platform.runtime_admin_defaults import (
    ENFORCEMENT_SETTINGS_DEFAULTS,
    ENFORCEMENT_TEMPLATE_DEFAULTS,
    TELEGRAM_RUNTIME_SETTINGS_DEFAULTS,
)

from ..context import APIContainer


DETECTION_LIST_KEYS = (
    "pure_mobile_asns",
    "pure_home_asns",
    "mixed_asns",
    "allowed_isp_keywords",
    "home_isp_keywords",
    "exclude_isp_keywords",
)
ACCESS_LIST_KEYS = ("admin_tg_ids", "moderator_tg_ids", "viewer_tg_ids", "exempt_tg_ids", "exempt_ids")
TELEGRAM_ENV_FIELDS = {
    "TG_MAIN_BOT_TOKEN": True,
    "TG_ADMIN_BOT_TOKEN": True,
    "TG_ADMIN_BOT_USERNAME": False,
}
ACCESS_ENV_FIELDS = {
    "PANEL_LOCAL_USERNAME": False,
    "PANEL_LOCAL_PASSWORD": True,
    "MOBGUARD_MODULE_SECRET_KEY": True,
}
TELEGRAM_CONFIG_KEYS = tuple(TELEGRAM_RUNTIME_SETTINGS_DEFAULTS.keys())
ENFORCEMENT_CONFIG_KEYS = tuple(ENFORCEMENT_SETTINGS_DEFAULTS.keys()) + tuple(
    ENFORCEMENT_TEMPLATE_DEFAULTS.keys()
)


def coerce_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coerce_int_list(values: list[Any]) -> list[int]:
    result: list[int] = []
    for value in values:
        coerced = coerce_optional_int(value)
        if coerced is not None:
            result.append(coerced)
    return result


def load_runtime_config(container: APIContainer) -> dict[str, Any]:
    return normalize_runtime_bound_settings(
        read_json_file(str(container.runtime.config_path)),
        container.runtime.runtime_dir,
    )


def load_env_values(container: APIContainer) -> dict[str, str]:
    return read_env_file(str(container.runtime.env_path))


def get_auth_capabilities(container: APIContainer, env_values: Optional[dict[str, str]] = None) -> dict[str, Any]:
    values = env_values or load_env_values(container)
    telegram_enabled = bool(values.get("TG_ADMIN_BOT_TOKEN") and values.get("TG_ADMIN_BOT_USERNAME"))
    local_enabled = bool(values.get("PANEL_LOCAL_USERNAME") and values.get("PANEL_LOCAL_PASSWORD"))
    return {
        "telegram_enabled": telegram_enabled,
        "bot_username": values.get("TG_ADMIN_BOT_USERNAME", "") if telegram_enabled else "",
        "local_enabled": local_enabled,
        "local_username_hint": values.get("PANEL_LOCAL_USERNAME", "") if local_enabled else "",
    }


def serialize_env_fields(
    container: APIContainer,
    field_map: dict[str, bool],
    env_values: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    values = env_values or load_env_values(container)
    return {
        key: env_field_payload(key, values, masked=masked, restart_required=True)
        for key, masked in field_map.items()
    }


def normalize_runtime_settings(
    config: dict[str, Any],
    defaults: dict[str, Any],
    aliases: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    aliases = aliases or {}
    settings = config.get("settings", {})
    normalized: dict[str, Any] = {}
    for key, default in defaults.items():
        if key in settings:
            normalized[key] = settings[key]
            continue
        alias_candidates = [legacy for legacy, canonical in aliases.items() if canonical == key]
        alias_value = next((settings.get(alias) for alias in alias_candidates if alias in settings), default)
        normalized[key] = alias_value
    return normalized


def write_runtime_settings(
    container: APIContainer,
    settings_updates: dict[str, Any],
    *,
    remove_keys: Optional[list[str]] = None,
) -> dict[str, Any]:
    runtime_config = read_json_file(str(container.runtime.config_path))
    runtime_config.setdefault("settings", {})
    for key, value in settings_updates.items():
        runtime_config["settings"][key] = value
    for key in remove_keys or []:
        runtime_config["settings"].pop(key, None)
    updated = update_json_file(str(container.runtime.config_path), {"settings": runtime_config["settings"]})
    container.runtime.reload_config()
    container.store.sync_runtime_config(container.runtime.config)
    return updated


def panel_client(container: APIContainer) -> PanelClient:
    runtime_config = load_runtime_config(container)
    env_values = load_env_values(container)
    settings = runtime_config.get("settings", {})
    remnawave_url = str(settings.get("remnawave_api_url") or settings.get("panel_url") or "").strip()
    remnawave_token = env_values.get("REMNAWAVE_API_TOKEN") or env_values.get("PANEL_TOKEN", "")
    return PanelClient(remnawave_url, remnawave_token)


def enrich_panel_user_devices(client: PanelClient, panel_user: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not isinstance(panel_user, dict):
        return panel_user
    if any(
        key in panel_user and isinstance(panel_user.get(key), list) and panel_user.get(key)
        for key in ("hwidDevices", "hwid_devices", "devices", "clients")
    ):
        return panel_user

    user_uuid = str(panel_user.get("uuid") or "").strip()
    if not user_uuid:
        return panel_user

    devices = client.get_user_hwid_devices(user_uuid)
    if not devices:
        return panel_user

    enriched = dict(panel_user)
    enriched["hwidDevices"] = devices
    if enriched.get("hwidDeviceCount") in (None, ""):
        enriched["hwidDeviceCount"] = len(devices)
    return enriched


def enrich_panel_user_usage_context(client: PanelClient, panel_user: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    enriched = enrich_panel_user_devices(client, panel_user)
    if not isinstance(enriched, dict):
        return enriched
    if isinstance(enriched.get("usageProfileTrafficStats"), dict):
        return enriched

    user_uuid = str(enriched.get("uuid") or "").strip()
    if not user_uuid:
        return enriched

    traffic_stats = client.get_user_traffic_stats(user_uuid)
    if not traffic_stats:
        return enriched

    payload = dict(enriched)
    payload["usageProfileTrafficStats"] = traffic_stats
    return payload


def _runtime_identity_columns(query: str) -> list[tuple[str, Any]]:
    candidates: list[tuple[str, Any]] = []
    if query.isdigit():
        candidates.append(("system_id", int(query)))
        candidates.append(("telegram_id", query))
    if len(query) > 20 and "-" in query:
        candidates.append(("uuid", query))
    candidates.append(("username", query))
    candidates.append(("uuid", query))
    unique: list[tuple[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for column, value in candidates:
        marker = (column, str(value))
        if marker in seen:
            continue
        seen.add(marker)
        unique.append((column, value))
    return unique


def get_runtime_user_match(store: Any, identifier: str) -> Optional[dict[str, Any]]:
    query = identifier.strip()
    if not query:
        return None
    with store._connect() as conn:
        for column, value in _runtime_identity_columns(query):
            exact = conn.execute(
                f"""
                SELECT uuid, username, system_id, telegram_id, updated_at
                FROM review_cases
                WHERE {column} = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (value,),
            ).fetchone()
            if exact:
                return dict(exact)
        like = f"%{query}%"
        row = conn.execute(
            """
            SELECT uuid, username, system_id, telegram_id, updated_at
            FROM review_cases
            WHERE uuid LIKE ? OR username LIKE ? OR telegram_id LIKE ? OR CAST(system_id AS TEXT) LIKE ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (like, like, like, like),
        ).fetchone()
    return dict(row) if row else None


def search_runtime_users(store: Any, query: str) -> list[dict[str, Any]]:
    normalized = query.strip()
    if not normalized:
        return []
    with store._connect() as conn:
        exact_rows: list[Any] = []
        for column, value in _runtime_identity_columns(normalized):
            exact_rows.extend(
                conn.execute(
                    f"""
                    SELECT uuid, username, system_id, telegram_id, updated_at
                    FROM review_cases
                    WHERE {column} = ?
                    ORDER BY updated_at DESC
                    LIMIT 20
                    """,
                    (value,),
                ).fetchall()
            )
        if exact_rows:
            deduped: list[dict[str, Any]] = []
            seen: set[tuple[Any, ...]] = set()
            for row in sorted(exact_rows, key=lambda item: str(item["updated_at"] or ""), reverse=True):
                marker = (row["uuid"], row["username"], row["system_id"], row["telegram_id"])
                if marker in seen:
                    continue
                seen.add(marker)
                deduped.append(dict(row))
                if len(deduped) >= 20:
                    break
            return deduped

        search = f"%{normalized}%"
        rows = conn.execute(
            """
            SELECT uuid, username, system_id, telegram_id, MAX(updated_at) AS updated_at
            FROM review_cases
            WHERE uuid LIKE ? OR username LIKE ? OR telegram_id LIKE ? OR CAST(system_id AS TEXT) LIKE ?
            GROUP BY uuid, username, system_id, telegram_id
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (search, search, search, search),
        ).fetchall()
    return [dict(row) for row in rows]


def resolve_user_identity(container: APIContainer, store: Any, identifier: str) -> dict[str, Any]:
    runtime_match = get_runtime_user_match(store, identifier)
    client = panel_client(container)
    panel_user = enrich_panel_user_usage_context(client, client.get_user_data(identifier))
    uuid = (panel_user or {}).get("uuid") or (runtime_match or {}).get("uuid")
    username = (panel_user or {}).get("username") or (runtime_match or {}).get("username")
    system_id = (
        (panel_user or {}).get("id")
        if (panel_user or {}).get("id") is not None
        else (runtime_match or {}).get("system_id")
    )
    telegram_id = (
        (panel_user or {}).get("telegramId")
        if (panel_user or {}).get("telegramId") is not None
        else (runtime_match or {}).get("telegram_id")
    )
    if not any(value not in (None, "") for value in (uuid, username, system_id, telegram_id)):
        raise HTTPException(status_code=404, detail="User not found")
    subject_key = subject_key_from_identity(
        {
            "uuid": uuid,
            "username": username,
            "system_id": system_id,
            "telegram_id": telegram_id,
        }
    )
    return {
        "uuid": uuid,
        "username": username,
        "system_id": system_id,
        "telegram_id": telegram_id,
        "subject_key": subject_key,
        "panel_user": panel_user,
    }


def build_user_lookup_clause(identity: dict[str, Any]) -> tuple[str, list[Any]]:
    if identity.get("subject_key"):
        return "subject_key = ?", [str(identity["subject_key"])]
    clauses: list[str] = []
    params: list[Any] = []
    if identity.get("uuid"):
        clauses.append("uuid = ?")
        params.append(identity["uuid"])
    if identity.get("system_id") not in (None, ""):
        clauses.append("system_id = ?")
        params.append(int(identity["system_id"]))
    if identity.get("telegram_id") not in (None, ""):
        clauses.append("telegram_id = ?")
        params.append(str(identity["telegram_id"]))
    if identity.get("username"):
        clauses.append("username = ?")
        params.append(identity["username"])
    if not clauses:
        raise HTTPException(status_code=404, detail="User lookup fields are unavailable")
    return " OR ".join(clauses), params


def _parse_optional_json(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _coerce_datetime_filter(value: Any, *, end_of_day: bool = False) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) == 10:
        suffix = "T23:59:59" if end_of_day else "T00:00:00"
        return f"{raw}{suffix}"
    return raw


def _analysis_event_select(conn: Any, store: Any) -> str:
    analysis_event_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(analysis_events)").fetchall()
    } if store._table_exists(conn, "analysis_events") else set()
    fields = [
        "id",
        "created_at",
        "ip",
        "tag",
        "verdict",
        "confidence_band",
        "score",
        "isp",
        "asn",
    ]
    for optional_column in (
        "module_id",
        "module_name",
        "case_scope_key",
        "device_scope_key",
        "scope_type",
        "client_device_id",
        "client_device_label",
        "client_os_family",
        "client_app_name",
        "country",
        "region",
        "city",
    ):
        if optional_column in analysis_event_columns:
            fields.append(optional_column)
        else:
            fields.append(f"NULL AS {optional_column}")
    for optional_column in ("reasons_json", "signal_flags_json", "bundle_json"):
        if optional_column in analysis_event_columns:
            fields.append(optional_column)
        else:
            fields.append(f"NULL AS {optional_column}")
    return ", ".join(fields)


def _violation_select(conn: Any, store: Any) -> str:
    violation_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(violations)").fetchall()
    } if store._table_exists(conn, "violations") else set()
    fields = [
        "uuid",
        "strikes",
        "unban_time",
        "last_forgiven",
        "last_strike_time",
        "warning_time",
        "warning_count",
    ]
    for optional_column in (
        "restriction_mode",
        "saved_traffic_limit_bytes",
        "saved_traffic_limit_strategy",
        "applied_traffic_limit_bytes",
    ):
        if optional_column in violation_columns:
            fields.append(optional_column)
        else:
            fields.append(f"NULL AS {optional_column}")
    return ", ".join(fields)


def _review_case_select(conn: Any, store: Any) -> str:
    review_case_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(review_cases)").fetchall()
    } if store._table_exists(conn, "review_cases") else set()
    fields = [
        "id",
        "status",
        "review_reason",
        "ip",
        "verdict",
        "confidence_band",
        "opened_at",
        "updated_at",
    ]
    for optional_column in ("module_id", "module_name"):
        if optional_column in review_case_columns:
            fields.append(optional_column)
        else:
            fields.append(f"NULL AS {optional_column}")
    return ", ".join(fields)


def _enrich_analysis_event_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    reasons = _parse_optional_json(payload.pop("reasons_json", None), [])
    signal_flags = _parse_optional_json(payload.pop("signal_flags_json", None), {})
    bundle = _parse_optional_json(payload.pop("bundle_json", None), None)
    payload["reasons"] = reasons
    payload["signal_flags"] = signal_flags
    payload["bundle"] = bundle
    provider_evidence = signal_flags.get("provider_evidence") if isinstance(signal_flags, dict) else None
    if isinstance(provider_evidence, dict):
        payload["provider_evidence"] = provider_evidence
    else:
        payload["provider_evidence"] = {}
    payload["inbound_tag"] = payload.get("tag")
    payload["target_ip"] = payload.get("ip")
    payload["target_scope_type"] = payload.get("scope_type") or "ip_only"
    payload["device_display"] = (
        payload.get("client_device_label")
        or payload.get("client_os_family")
        or payload.get("client_device_id")
        or None
    )
    return payload


def build_user_card(store: Any, identity: dict[str, Any]) -> dict[str, Any]:
    lookup_clause, lookup_params = build_user_lookup_clause(identity)
    rules_state = store.get_live_rules_state()
    with store._connect() as conn:
        has_violations = store._table_exists(conn, "violations")
        has_violation_history = store._table_exists(conn, "violation_history")
        has_active_trackers = store._table_exists(conn, "active_trackers")
        has_ip_history = store._table_exists(conn, "ip_history")
        violation = conn.execute(
            f"SELECT {_violation_select(conn, store)} FROM violations WHERE uuid = ?",
            (identity.get("uuid"),),
        ).fetchone() if identity.get("uuid") and has_violations else None
        history = conn.execute(
            """
            SELECT uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp
            FROM violation_history
            WHERE uuid = ?
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            (identity.get("uuid"),),
        ).fetchall() if identity.get("uuid") and has_violation_history else []
        trackers = conn.execute(
            """
            SELECT key, start_time, last_seen
            FROM active_trackers
            WHERE key LIKE ?
            ORDER BY last_seen DESC
            LIMIT 20
            """,
            (f"{identity.get('uuid')}:%",),
        ).fetchall() if identity.get("uuid") and has_active_trackers else []
        ip_history = conn.execute(
            """
            SELECT ip, timestamp
            FROM ip_history
            WHERE uuid = ?
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            (identity.get("uuid"),),
        ).fetchall() if identity.get("uuid") and has_ip_history else []
        review_case_select = _review_case_select(conn, store)
        review_cases = conn.execute(
            f"""
            SELECT {review_case_select}
            FROM review_cases
            WHERE {lookup_clause}
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            lookup_params,
        ).fetchall()
        analysis_event_select = _analysis_event_select(conn, store)
        recent_events = conn.execute(
            f"""
            SELECT {analysis_event_select}
            FROM analysis_events
            WHERE {lookup_clause}
            ORDER BY created_at DESC
            LIMIT 20
            """,
            lookup_params,
        ).fetchall()
        active_ban_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM violations WHERE uuid = ? AND unban_time > datetime('now')",
            (identity.get("uuid"),),
        ).fetchone()["cnt"] if identity.get("uuid") and has_violations else 0

    exempt_system_ids = set(coerce_int_list(rules_state["rules"].get("exempt_ids", [])))
    exempt_tg_ids = set(coerce_int_list(rules_state["rules"].get("exempt_tg_ids", [])))
    system_id = identity.get("system_id")
    telegram_id = identity.get("telegram_id")
    usage_profile = build_usage_profile_snapshot(
        store,
        identity,
        panel_user=identity.get("panel_user"),
    )
    return {
        "identity": {
            "uuid": identity.get("uuid"),
            "username": identity.get("username"),
            "system_id": coerce_optional_int(system_id),
            "telegram_id": str(telegram_id) if telegram_id not in (None, "") else None,
        },
        "panel_user": identity.get("panel_user"),
        "violation": dict(violation) if violation else None,
        "history": [dict(row) for row in history],
        "active_trackers": [dict(row) for row in trackers],
        "ip_history": [dict(row) for row in ip_history],
        "review_cases": [dict(row) for row in review_cases],
        "analysis_events": [_enrich_analysis_event_row(dict(row)) for row in recent_events],
        "usage_profile": usage_profile,
        "flags": {
            "exempt_system_id": coerce_optional_int(system_id) in exempt_system_ids if system_id not in (None, "") else False,
            "exempt_telegram_id": coerce_optional_int(telegram_id) in exempt_tg_ids if telegram_id not in (None, "") else False,
            "active_ban": bool(active_ban_count),
            "active_warning": bool(violation and violation["warning_time"]),
        },
    }


def list_analysis_events(store: Any, filters: dict[str, Any]) -> dict[str, Any]:
    page = max(int(filters.get("page", 1) or 1), 1)
    page_size = min(max(int(filters.get("page_size", 50) or 50), 1), 200)
    sort = str(filters.get("sort") or "created_desc").strip().lower()
    order_by = "ae.created_at ASC" if sort == "created_asc" else "ae.created_at DESC"
    clauses: list[str] = []
    params: list[Any] = []

    if filters.get("ip"):
        clauses.append("ae.ip = ?")
        params.append(str(filters["ip"]).strip())
    if filters.get("device_id"):
        clauses.append("ae.client_device_id = ?")
        params.append(str(filters["device_id"]).strip())
    if filters.get("module_id"):
        clauses.append("ae.module_id = ?")
        params.append(str(filters["module_id"]).strip())
    if filters.get("tag"):
        clauses.append("ae.tag = ?")
        params.append(str(filters["tag"]).strip())
    if filters.get("provider"):
        clauses.append("ae.isp LIKE ?")
        params.append(f"%{str(filters['provider']).strip()}%")
    if filters.get("asn") not in (None, ""):
        clauses.append("ae.asn = ?")
        params.append(int(filters["asn"]))
    if filters.get("verdict"):
        clauses.append("ae.verdict = ?")
        params.append(str(filters["verdict"]).strip())
    if filters.get("confidence_band"):
        clauses.append("ae.confidence_band = ?")
        params.append(str(filters["confidence_band"]).strip())
    if filters.get("created_from"):
        clauses.append("ae.created_at >= ?")
        params.append(_coerce_datetime_filter(filters["created_from"], end_of_day=False))
    if filters.get("created_to"):
        clauses.append("ae.created_at <= ?")
        params.append(_coerce_datetime_filter(filters["created_to"], end_of_day=True))
    if filters.get("q"):
        search = f"%{str(filters['q']).strip()}%"
        clauses.append(
            "(ae.ip LIKE ? OR ae.isp LIKE ? OR ae.tag LIKE ? OR ae.module_name LIKE ? OR ae.client_device_id LIKE ? OR ae.client_device_label LIKE ?)"
        )
        params.extend([search] * 6)
    if filters.get("has_review_case") is not None:
        has_case = str(filters["has_review_case"]).lower() in {"1", "true", "yes"}
        clauses.append(
            (
                "EXISTS (SELECT 1 FROM review_cases rc WHERE rc.case_scope_key = ae.case_scope_key AND rc.status != 'MERGED')"
                if has_case
                else "NOT EXISTS (SELECT 1 FROM review_cases rc WHERE rc.case_scope_key = ae.case_scope_key AND rc.status != 'MERGED')"
            )
        )

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with store._connect() as conn:
        select_sql = _analysis_event_select(conn, store)
        count = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM analysis_events ae {where_sql}",
            params,
        ).fetchone()["cnt"]
        rows = conn.execute(
            f"""
            SELECT {select_sql},
                   EXISTS (
                       SELECT 1
                       FROM review_cases rc
                       WHERE rc.case_scope_key = ae.case_scope_key AND rc.status != 'MERGED'
                   ) AS has_review_case,
                   (
                       SELECT rc.id
                       FROM review_cases rc
                       WHERE rc.case_scope_key = ae.case_scope_key AND rc.status != 'MERGED'
                       ORDER BY CASE rc.status WHEN 'OPEN' THEN 0 ELSE 1 END, rc.updated_at DESC, rc.id DESC
                       LIMIT 1
                   ) AS review_case_id,
                   (
                       SELECT rc.status
                       FROM review_cases rc
                       WHERE rc.case_scope_key = ae.case_scope_key AND rc.status != 'MERGED'
                       ORDER BY CASE rc.status WHEN 'OPEN' THEN 0 ELSE 1 END, rc.updated_at DESC, rc.id DESC
                       LIMIT 1
                   ) AS review_case_status
            FROM analysis_events ae
            {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()

    items = [_enrich_analysis_event_row(dict(row)) for row in rows]
    for item in items:
        review_case_id = item.get("review_case_id")
        item["review_url"] = store.build_review_url(int(review_case_id)) if review_case_id not in (None, "") else ""
    return {
        "items": items,
        "count": int(count or 0),
        "page": page,
        "page_size": page_size,
    }


def build_user_export_payload(store: Any, identifier: str, identity: dict[str, Any]) -> dict[str, Any]:
    card = build_user_card(store, identity)
    lookup_fields = {
        key: value
        for key, value in card["identity"].items()
        if value not in (None, "")
    }
    return {
        "export_meta": {
            "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
            "identifier": identifier,
            "lookup_fields": lookup_fields,
            "record_counts": {
                "review_cases": len(card.get("review_cases", [])),
                "analysis_events": len(card.get("analysis_events", [])),
                "history": len(card.get("history", [])),
                "active_trackers": len(card.get("active_trackers", [])),
                "ip_history": len(card.get("ip_history", [])),
                "usage_profile_signals": len((card.get("usage_profile") or {}).get("soft_reasons", [])),
            },
        },
        **card,
    }
