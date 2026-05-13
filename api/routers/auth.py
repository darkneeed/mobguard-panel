from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from ..dependencies import get_container, get_session, require_permission
from ..permissions import PERMISSION_SETTINGS_ACCESS_WRITE
from ..schemas.auth import LocalLoginRequest, TelegramVerifyRequest, TotpChallengeRequest, TotpCodeRequest
from ..services.admin_audit import record_admin_action
from ..services.auth import (
    auth_start_payload,
    clear_session_cookie,
    disable_owner_totp,
    local_login,
    totp_confirm_setup,
    totp_setup,
    totp_verify,
    verify_telegram_login,
)


router = APIRouter(prefix="/admin", tags=["auth"])


@router.post("/auth/telegram/start")
def auth_start(container=Depends(get_container)) -> dict[str, Any]:
    return auth_start_payload(container)


@router.post("/auth/telegram/verify")
def auth_verify(body: TelegramVerifyRequest, response: Response, container=Depends(get_container)) -> dict[str, Any]:
    return verify_telegram_login(container, body.payload, response)


@router.post("/auth/local/login")
def auth_local(body: LocalLoginRequest, response: Response, container=Depends(get_container)) -> dict[str, Any]:
    return local_login(container, body.username, body.password, response)


@router.post("/auth/totp/setup")
def auth_totp_setup(body: TotpChallengeRequest, container=Depends(get_container)) -> dict[str, Any]:
    return totp_setup(container, body.challenge_token)


@router.post("/auth/totp/confirm")
def auth_totp_confirm(
    body: TotpCodeRequest,
    response: Response,
    container=Depends(get_container),
) -> dict[str, Any]:
    return totp_confirm_setup(container, body.challenge_token, body.code, response)


@router.post("/auth/totp/verify")
def auth_totp_verify(
    body: TotpCodeRequest,
    response: Response,
    container=Depends(get_container),
) -> dict[str, Any]:
    return totp_verify(container, body.challenge_token, body.code, response)


@router.post("/auth/totp/disable-all")
def auth_totp_disable_all(
    session: dict[str, Any] = Depends(require_permission(PERMISSION_SETTINGS_ACCESS_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    result = disable_owner_totp(container)
    record_admin_action(
        container,
        session,
        action="auth.totp.disable_all",
        target_type="owner_security",
        target_id="owner_totp",
        details={
            "cleared_identity_count": int(result.get("cleared_identity_count") or 0),
            "cleared_challenge_count": int(result.get("cleared_challenge_count") or 0),
        },
    )
    return result


@router.post("/logout")
def logout(response: Response, session: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, bool]:
    container.store.delete_admin_session(session["token"])
    clear_session_cookie(container, response)
    return {"ok": True}


@router.get("/me")
def get_me(session: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    return {
        "telegram_id": session["telegram_id"],
        "username": session.get("username"),
        "first_name": session.get("first_name"),
        "expires_at": session["expires_at"],
        "subject": session.get("subject", ""),
        "auth_method": session.get("auth_method", ""),
        "role": session.get("role", ""),
        "permissions": list(session.get("permissions") or []),
        "totp_enabled": bool(session.get("totp_enabled")),
        "totp_verified": bool(session.get("totp_verified")),
        "totp_verified_at": session.get("totp_verified_at", ""),
        "payload": session.get("payload", {}),
    }
