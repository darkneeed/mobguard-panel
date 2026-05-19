from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from mobguard_platform.runtime import get_env_file_status, update_env_file
from mobguard_platform.runtime_admin_defaults import (
    build_applied_runtime_notification,
    ENFORCEMENT_SETTINGS_DEFAULTS,
    ENFORCEMENT_TEMPLATE_DEFAULTS,
    normalize_telegram_runtime_settings,
)

from ..context import APIContainer
from .automation_status import build_automation_status
from .reviews import detection_recheck_needed, recheck_provider_sensitive_reviews, update_rules
from .runtime_state import (
    ACCESS_ENV_FIELDS,
    ACCESS_LIST_KEYS,
    ENFORCEMENT_CONFIG_KEYS,
    TELEGRAM_CONFIG_KEYS,
    TELEGRAM_ENV_FIELDS,
    get_auth_capabilities,
    load_env_values,
    load_runtime_config,
    normalize_runtime_settings,
    serialize_env_fields,
    write_runtime_settings,
)

ACCESS_RUNTIME_SETTINGS_DEFAULTS = {
    "panel_name": "MobGuard",
    "panel_logo_url": "",
}

TELEGRAM_TOPIC_SETTINGS_TO_EVENT = {
    "tg_topic_review": "review",
    "tg_topic_warning_only": "warning_only",
    "tg_topic_warning": "warning",
    "tg_topic_ban": "ban",
    "tg_topic_usage_profile_risk": "usage_profile_risk",
    "tg_topic_violation_continues": "violation_continues",
    "tg_topic_traffic_limit_exceeded": "traffic_limit_exceeded",
}


def _sync_topic_routing(container: APIContainer, settings_payload: dict[str, Any]) -> None:
    rows: list[tuple[str, int, str]] = []
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    for setting_key, event_key in TELEGRAM_TOPIC_SETTINGS_TO_EVENT.items():
        if setting_key not in settings_payload:
            continue
        try:
            topic_id = int(settings_payload.get(setting_key) or 0)
        except (TypeError, ValueError):
            topic_id = 0
        rows.append((event_key, topic_id, now))
    if not rows:
        return
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "telegram_topic_routing"):
            return
        for event_key, topic_id, updated_at in rows:
            conn.execute(
                """
                INSERT INTO telegram_topic_routing (event_key, topic_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(event_key) DO UPDATE SET
                    topic_id = excluded.topic_id,
                    updated_at = excluded.updated_at
                """,
                (event_key, topic_id, updated_at),
            )
        conn.commit()


def _runtime_settings(container: APIContainer) -> dict[str, Any]:
    runtime_config = load_runtime_config(container)
    settings = runtime_config.get("settings", {})
    return dict(settings) if isinstance(settings, dict) else {}


def _core_runs_embedded(container: APIContainer) -> bool:
    if not hasattr(container.store, "get_service_heartbeat"):
        return True
    heartbeat = container.store.get_service_heartbeat("mobguard-core")
    return str(heartbeat.get("status") or "") == "missing"


def _notify_applied_runtime_change_if_embedded(
    container: APIContainer,
    previous_settings: dict[str, Any],
    current_settings: dict[str, Any],
) -> None:
    notifier = getattr(container, "telegram_notifier", None)
    if notifier is None or not _core_runs_embedded(container):
        return
    notice = build_applied_runtime_notification(previous_settings, current_settings)
    if not notice:
        return
    if notice.get("force_send") and hasattr(notifier, "notify_admin_force"):
        asyncio.run(
            notifier.notify_admin_force(
                str(notice["message"]),
                dedupe_key="embedded-config-applied-force",
            )
        )
        return
    if notice.get("admin_notifications_enabled"):
        asyncio.run(
            notifier.notify_admin(
                str(notice["message"]),
                dedupe_key="embedded-config-applied",
            )
        )


def get_detection_settings(container: APIContainer) -> dict[str, Any]:
    state = container.store.get_live_rules_state()
    return {
        "revision": state["revision"],
        "updated_at": state["updated_at"],
        "updated_by": state["updated_by"],
        "rules": state["rules"],
    }


def update_detection_settings(
    container: APIContainer,
    payload: dict[str, Any],
    actor: str,
    actor_tg_id: int,
    revision: int | None,
    updated_at: str | None,
) -> dict[str, Any]:
    previous_settings = _runtime_settings(container)
    result = update_rules(
        container.store,
        payload,
        actor,
        actor_tg_id,
        expected_revision=revision,
        expected_updated_at=updated_at,
    )
    if detection_recheck_needed(payload):
        asyncio.run(recheck_provider_sensitive_reviews(container, actor, actor_tg_id, skip_on_busy=True))
    _notify_applied_runtime_change_if_embedded(
        container,
        previous_settings,
        _runtime_settings(container),
    )
    return result


def get_access_settings(container: APIContainer) -> dict[str, Any]:
    state = container.store.get_live_rules_state()
    env_values = load_env_values(container)
    env_status = get_env_file_status(str(container.runtime.env_path))
    runtime_config = load_runtime_config(container)
    access_settings = normalize_runtime_settings(
        runtime_config,
        ACCESS_RUNTIME_SETTINGS_DEFAULTS,
    )
    owner_security = (
        container.store.get_owner_totp_summary()
        if hasattr(container.store, "get_owner_totp_summary")
        else {
            "owner_identity_count": 0,
            "enabled_owner_count": 0,
            "pending_challenge_count": 0,
            "totp_enabled": False,
        }
    )
    return {
        "revision": state["revision"],
        "updated_at": state["updated_at"],
        "updated_by": state["updated_by"],
        "lists": {key: state["rules"].get(key, []) for key in ACCESS_LIST_KEYS},
        "settings": access_settings,
        "env": serialize_env_fields(container, ACCESS_ENV_FIELDS, env_values),
        "auth": get_auth_capabilities(container, env_values),
        "owner_security": owner_security,
        "env_file_path": env_status["path"],
        "env_file_writable": env_status["writable"],
    }


def update_access_settings(
    container: APIContainer,
    payload: dict[str, Any],
    actor: str,
    actor_tg_id: int,
    revision: int | None,
    updated_at: str | None,
) -> dict[str, Any]:
    rules_payload = {key: payload.get("lists", {}).get(key) for key in ACCESS_LIST_KEYS if key in payload.get("lists", {})}
    if rules_payload:
        update_rules(
            container.store,
            rules_payload,
            actor,
            actor_tg_id,
            expected_revision=revision,
            expected_updated_at=updated_at,
        )
    settings_updates = {
        key: payload.get("settings", {}).get(key)
        for key in ACCESS_RUNTIME_SETTINGS_DEFAULTS
        if key in payload.get("settings", {})
    }
    if settings_updates:
        write_runtime_settings(container, settings_updates)
    env_updates = {key: payload.get("env", {}).get(key) for key in ACCESS_ENV_FIELDS if key in payload.get("env", {})}
    if env_updates:
        try:
            update_env_file(str(container.runtime.env_path), env_updates)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return get_access_settings(container)


def get_telegram_settings(container: APIContainer) -> dict[str, Any]:
    runtime_config = load_runtime_config(container)
    env_values = load_env_values(container)
    env_status = get_env_file_status(str(container.runtime.env_path))
    settings = normalize_telegram_runtime_settings(runtime_config.get("settings", {}))
    return {
        "settings": settings,
        "env": serialize_env_fields(container, TELEGRAM_ENV_FIELDS, env_values),
        "capabilities": {
            "admin_bot_enabled": bool(env_values.get("TG_ADMIN_BOT_TOKEN") and env_values.get("TG_ADMIN_BOT_USERNAME")),
            "user_bot_enabled": bool(env_values.get("TG_MAIN_BOT_TOKEN")),
        },
        "env_file_path": env_status["path"],
        "env_file_writable": env_status["writable"],
    }


def update_telegram_settings(container: APIContainer, payload: dict[str, Any]) -> dict[str, Any]:
    previous_settings = _runtime_settings(container)
    settings_updates = {
        key: payload.get("settings", {}).get(key)
        for key in TELEGRAM_CONFIG_KEYS
        if key in payload.get("settings", {})
    }
    if settings_updates:
        write_runtime_settings(container, settings_updates)
        _sync_topic_routing(container, settings_updates)
    env_updates = {key: payload.get("env", {}).get(key) for key in TELEGRAM_ENV_FIELDS if key in payload.get("env", {})}
    if env_updates:
        try:
            update_env_file(str(container.runtime.env_path), env_updates)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    _notify_applied_runtime_change_if_embedded(
        container,
        previous_settings,
        _runtime_settings(container),
    )
    return get_telegram_settings(container)


def get_enforcement_settings(container: APIContainer) -> dict[str, Any]:
    runtime_config = load_runtime_config(container)
    enforcement_settings = normalize_runtime_settings(
        runtime_config,
        ENFORCEMENT_SETTINGS_DEFAULTS,
        aliases={"warning_timeout": "warning_timeout_seconds"},
    )
    templates = {
        key: runtime_config.get("settings", {}).get(key, default)
        for key, default in ENFORCEMENT_TEMPLATE_DEFAULTS.items()
    }
    return {
        "settings": {**enforcement_settings, **templates},
        "automation_status": build_automation_status(container),
    }


def update_enforcement_settings(container: APIContainer, payload: dict[str, Any]) -> dict[str, Any]:
    previous_settings = _runtime_settings(container)
    settings_updates = {
        key: payload.get("settings", {}).get(key)
        for key in ENFORCEMENT_CONFIG_KEYS
        if key in payload.get("settings", {})
    }
    if settings_updates:
        write_runtime_settings(container, settings_updates, remove_keys=["warning_timeout"])
    _notify_applied_runtime_change_if_embedded(
        container,
        previous_settings,
        _runtime_settings(container),
    )
    return get_enforcement_settings(container)
