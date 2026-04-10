from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from .context import APIContainer


def get_container(request: Request) -> APIContainer:
    return request.app.state.container


def get_session(request: Request) -> dict[str, Any]:
    container = get_container(request)
    session_token = request.cookies.get(container.session_cookie_name)
    if not session_token:
        raise HTTPException(status_code=401, detail="Missing session cookie")
    session = container.store.get_admin_session(session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session
