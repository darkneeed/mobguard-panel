from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from ..dependencies import get_container, get_session
from ..schemas.auth import LocalLoginRequest, TelegramVerifyRequest
from ..services.auth import auth_start_payload, clear_session_cookie, local_login, verify_telegram_login


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
        "payload": session.get("payload", {}),
    }
