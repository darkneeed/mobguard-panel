from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Response

from mobguard_platform import verify_telegram_auth

from ..context import APIContainer
from .runtime_state import get_auth_capabilities, load_env_values


def build_local_session_payload(username: str) -> dict[str, Any]:
    return {
        "id": 0,
        "username": username,
        "first_name": "Local Admin",
        "auth_method": "local",
    }


def set_session_cookie(container: APIContainer, response: Response, token: str, max_age_seconds: int = 86400) -> None:
    response.set_cookie(
        key=container.session_cookie_name,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=container.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(container: APIContainer, response: Response) -> None:
    response.delete_cookie(
        key=container.session_cookie_name,
        httponly=True,
        secure=container.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def auth_start_payload(container: APIContainer) -> dict[str, Any]:
    env_values = load_env_values(container)
    rules_state = container.store.get_live_rules_state()
    return {
        **get_auth_capabilities(container, env_values),
        "review_ui_base_url": rules_state["rules"].get("settings", {}).get("review_ui_base_url", ""),
        "panel_name": "MobGuard Admin",
    }


def verify_telegram_login(container: APIContainer, payload: dict[str, Any], response: Response) -> dict[str, Any]:
    env_values = load_env_values(container)
    telegram_bot_token = env_values.get("TG_ADMIN_BOT_TOKEN", "")
    telegram_bot_username = env_values.get("TG_ADMIN_BOT_USERNAME", "")
    if not telegram_bot_token or not telegram_bot_username:
        raise HTTPException(status_code=400, detail="Telegram auth is not configured")
    ok, reason = verify_telegram_auth(payload, telegram_bot_token)
    if not ok:
        raise HTTPException(status_code=401, detail=reason)
    tg_id = int(payload.get("id", 0) or 0)
    if not tg_id or not container.store.is_admin_tg_id(tg_id):
        raise HTTPException(status_code=403, detail="Telegram account is not allowed")
    session = container.store.create_admin_session(payload)
    set_session_cookie(container, response, session["token"])
    return {
        "telegram_id": session["telegram_id"],
        "username": session.get("username"),
        "first_name": session.get("first_name"),
        "expires_at": session["expires_at"],
    }


def local_login(container: APIContainer, username: str, password: str, response: Response) -> dict[str, Any]:
    env_values = load_env_values(container)
    expected_username = env_values.get("PANEL_LOCAL_USERNAME", "")
    expected_password = env_values.get("PANEL_LOCAL_PASSWORD", "")
    if not expected_username or not expected_password:
        raise HTTPException(status_code=400, detail="Local auth is not configured")
    if not secrets.compare_digest(username, expected_username) or not secrets.compare_digest(password, expected_password):
        raise HTTPException(status_code=401, detail="Invalid local credentials")
    session = container.store.create_admin_session(build_local_session_payload(expected_username))
    set_session_cookie(container, response, session["token"])
    return {
        "telegram_id": session["telegram_id"],
        "username": session.get("username"),
        "first_name": session.get("first_name"),
        "expires_at": session["expires_at"],
        "payload": {"auth_method": "local"},
    }
