from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..dependencies import get_container, get_session
from ..schemas.reviews import RulesUpdateRequest
from ..schemas.settings import SettingsSectionUpdateRequest
from ..services import settings as settings_service


router = APIRouter(prefix="/admin/settings", tags=["settings"])


@router.get("/detection")
def get_detection_settings(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return settings_service.get_detection_settings(container)


@router.put("/detection")
def put_detection_settings(
    payload: RulesUpdateRequest,
    session: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.update_detection_settings(
        container,
        payload.rules,
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        payload.revision,
        payload.updated_at,
    )


@router.get("/access")
def get_access_settings(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return settings_service.get_access_settings(container)


@router.put("/access")
def put_access_settings(
    payload: SettingsSectionUpdateRequest,
    session: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.update_access_settings(
        container,
        payload.model_dump(),
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        payload.revision,
        payload.updated_at,
    )


@router.get("/telegram")
def get_telegram_settings(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return settings_service.get_telegram_settings(container)


@router.put("/telegram")
def put_telegram_settings(
    payload: SettingsSectionUpdateRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.update_telegram_settings(container, payload.model_dump())


@router.get("/enforcement")
def get_enforcement_settings(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return settings_service.get_enforcement_settings(container)


@router.put("/enforcement")
def put_enforcement_settings(
    payload: SettingsSectionUpdateRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.update_enforcement_settings(container, payload.model_dump())
