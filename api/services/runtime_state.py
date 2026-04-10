from __future__ import annotations

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
ACCESS_LIST_KEYS = ("admin_tg_ids", "exempt_tg_ids", "exempt_ids")
TELEGRAM_ENV_FIELDS = {
    "TG_MAIN_BOT_TOKEN": True,
    "TG_ADMIN_BOT_TOKEN": True,
    "TG_ADMIN_BOT_USERNAME": False,
}
ACCESS_ENV_FIELDS = {
    "PANEL_LOCAL_USERNAME": False,
    "PANEL_LOCAL_PASSWORD": True,
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
    panel_url = str(runtime_config.get("settings", {}).get("panel_url", "")).strip()
    panel_token = env_values.get("PANEL_TOKEN", "")
    return PanelClient(panel_url, panel_token)


def get_runtime_user_match(store: Any, identifier: str) -> Optional[dict[str, Any]]:
    query = identifier.strip()
    if not query:
        return None
    with store._connect() as conn:
        exact = conn.execute(
            """
            SELECT uuid, username, system_id, telegram_id, updated_at
            FROM review_cases
            WHERE uuid = ? OR username = ? OR telegram_id = ? OR CAST(system_id AS TEXT) = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (query, query, query, query),
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
    search = f"%{query.strip()}%"
    if not query.strip():
        return []
    with store._connect() as conn:
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
    panel_user = panel_client(container).get_user_data(identifier)
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
    return {
        "uuid": uuid,
        "username": username,
        "system_id": system_id,
        "telegram_id": telegram_id,
        "panel_user": panel_user,
    }


def build_user_lookup_clause(identity: dict[str, Any]) -> tuple[str, list[Any]]:
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


def build_user_card(store: Any, identity: dict[str, Any]) -> dict[str, Any]:
    lookup_clause, lookup_params = build_user_lookup_clause(identity)
    rules_state = store.get_live_rules_state()
    with store._connect() as conn:
        has_violations = store._table_exists(conn, "violations")
        has_violation_history = store._table_exists(conn, "violation_history")
        has_active_trackers = store._table_exists(conn, "active_trackers")
        has_ip_history = store._table_exists(conn, "ip_history")
        violation = conn.execute(
            "SELECT uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count FROM violations WHERE uuid = ?",
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
        review_cases = conn.execute(
            f"""
            SELECT id, status, review_reason, ip, verdict, confidence_band, opened_at, updated_at
            FROM review_cases
            WHERE {lookup_clause}
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            lookup_params,
        ).fetchall()
        recent_events = conn.execute(
            f"""
            SELECT id, created_at, ip, tag, verdict, confidence_band, score, isp, asn
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
        "analysis_events": [dict(row) for row in recent_events],
        "flags": {
            "exempt_system_id": coerce_optional_int(system_id) in exempt_system_ids if system_id not in (None, "") else False,
            "exempt_telegram_id": coerce_optional_int(telegram_id) in exempt_tg_ids if telegram_id not in (None, "") else False,
            "active_ban": bool(active_ban_count),
            "active_warning": bool(violation and violation["warning_time"]),
        },
    }
