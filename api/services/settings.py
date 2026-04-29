from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from mobguard_platform.runtime import get_env_file_status, update_env_file
from mobguard_platform.runtime_admin_defaults import (
    ENFORCEMENT_SETTINGS_DEFAULTS,
    ENFORCEMENT_TEMPLATE_DEFAULTS,
    normalize_telegram_runtime_settings,
)

from ..context import APIContainer
from .automation_status import build_automation_status
from .reviews import detection_recheck_needed, recheck_open_reviews, update_rules
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
    result = update_rules(
        container.store,
        payload,
        actor,
        actor_tg_id,
        expected_revision=revision,
        expected_updated_at=updated_at,
    )
    if detection_recheck_needed(payload):
        asyncio.run(recheck_open_reviews(container, actor, actor_tg_id, skip_on_busy=True))
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
    return {
        "revision": state["revision"],
        "updated_at": state["updated_at"],
        "updated_by": state["updated_by"],
        "lists": {key: state["rules"].get(key, []) for key in ACCESS_LIST_KEYS},
        "settings": access_settings,
        "env": serialize_env_fields(container, ACCESS_ENV_FIELDS, env_values),
        "auth": get_auth_capabilities(container, env_values),
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
    settings_updates = {
        key: payload.get("settings", {}).get(key)
        for key in TELEGRAM_CONFIG_KEYS
        if key in payload.get("settings", {})
    }
    if settings_updates:
        write_runtime_settings(container, settings_updates)
    env_updates = {key: payload.get("env", {}).get(key) for key in TELEGRAM_ENV_FIELDS if key in payload.get("env", {})}
    if env_updates:
        try:
            update_env_file(str(container.runtime.env_path), env_updates)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    settings_updates = {
        key: payload.get("settings", {}).get(key)
        for key in ENFORCEMENT_CONFIG_KEYS
        if key in payload.get("settings", {})
    }
    if settings_updates:
        write_runtime_settings(container, settings_updates, remove_keys=["warning_timeout"])
    return get_enforcement_settings(container)
