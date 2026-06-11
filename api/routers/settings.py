from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..dependencies import get_container, require_permission
from ..permissions import (
    PERMISSION_RULES_READ,
    PERMISSION_RULES_WRITE,
    PERMISSION_SETTINGS_ACCESS_READ,
    PERMISSION_SETTINGS_ACCESS_WRITE,
    PERMISSION_SETTINGS_ENFORCEMENT_READ,
    PERMISSION_SETTINGS_ENFORCEMENT_WRITE,
    PERMISSION_SETTINGS_TELEGRAM_READ,
    PERMISSION_SETTINGS_TELEGRAM_WRITE,
)
from ..schemas.reviews import RulesUpdateRequest
from ..schemas.settings import SettingsSectionUpdateRequest
from ..services.admin_audit import record_admin_action
from ..services import settings as settings_service
from ..services import config_health as config_health_service
from ..services import ai_optimizer as ai_optimizer_service


router = APIRouter(prefix="/admin/settings", tags=["settings"])


@router.get("/config-health")
def get_config_health_endpoint(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return config_health_service.get_config_health(container)



@router.get("/detection")
def get_detection_settings(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.get_detection_settings(container)


@router.put("/detection")
def put_detection_settings(
    payload: RulesUpdateRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    result = settings_service.update_detection_settings(
        container,
        payload.rules,
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        payload.revision,
        payload.updated_at,
    )
    record_admin_action(
        container,
        session,
        action="settings.detection.update",
        target_type="settings_section",
        target_id="detection",
        details={"keys": sorted(payload.rules.keys()) if isinstance(payload.rules, dict) else []},
    )
    return result


@router.get("/access")
def get_access_settings(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_SETTINGS_ACCESS_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.get_access_settings(container)


@router.put("/access")
def put_access_settings(
    payload: SettingsSectionUpdateRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_SETTINGS_ACCESS_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    result = settings_service.update_access_settings(
        container,
        payload.model_dump(),
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        payload.revision,
        payload.updated_at,
    )
    record_admin_action(
        container,
        session,
        action="settings.access.update",
        target_type="settings_section",
        target_id="access",
        details={"has_lists": bool(payload.lists), "has_settings": bool(payload.settings), "has_env": bool(payload.env)},
    )
    return result


@router.get("/telegram")
def get_telegram_settings(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_SETTINGS_TELEGRAM_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.get_telegram_settings(container)


@router.put("/telegram")
def put_telegram_settings(
    payload: SettingsSectionUpdateRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_SETTINGS_TELEGRAM_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    result = settings_service.update_telegram_settings(container, payload.model_dump())
    record_admin_action(
        container,
        session,
        action="settings.telegram.update",
        target_type="settings_section",
        target_id="telegram",
        details={"has_settings": bool(payload.settings), "has_env": bool(payload.env)},
    )
    return result


@router.get("/enforcement")
def get_enforcement_settings(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_SETTINGS_ENFORCEMENT_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return settings_service.get_enforcement_settings(container)


@router.put("/enforcement")
def put_enforcement_settings(
    payload: SettingsSectionUpdateRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_SETTINGS_ENFORCEMENT_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    result = settings_service.update_enforcement_settings(container, payload.model_dump())
    record_admin_action(
        container,
        session,
        action="settings.enforcement.update",
        target_type="settings_section",
        target_id="enforcement",
        details={"has_settings": bool(payload.settings)},
    )
    return result


@router.get("/ai-optimize/status")
def get_ai_optimize_status(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return ai_optimizer_service.get_optimizer_cooldown_status(container)


@router.post("/ai-optimize")
def post_ai_optimize(
    force: bool = False,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return ai_optimizer_service.generate_gemini_recommendations(container, force=force)
