from __future__ import annotations

import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from mobguard_platform.storage.sqlite import is_sqlite_busy_error

from ..dependencies import get_container, require_permission
from ..permissions import (
    PERMISSION_MODULES_READ,
    PERMISSION_MODULES_TOKEN_REVEAL,
    PERMISSION_MODULES_WRITE,
)
from ..schemas.modules import (
    EventBatchRequest,
    ModuleHeartbeatRequest,
    ModuleProvisioningRequest,
    ModuleRegisterRequest,
)
from ..services.admin_audit import record_admin_action
from ..services import modules as module_service


router = APIRouter(tags=["modules"])


def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return token.strip()


@router.post("/module/register")
def register_module(
    payload: ModuleRegisterRequest,
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return module_service.register_module(container, payload.model_dump(), _bearer_token(authorization))
    except module_service.ModuleStorageBusyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/module/heartbeat")
def module_heartbeat(
    payload: ModuleHeartbeatRequest,
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return module_service.record_module_heartbeat(container, payload.model_dump(), _bearer_token(authorization))
    except module_service.ModuleStorageBusyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/module/config")
def module_config(
    module_id: str = Query(...),
    protocol_version: str = Query(default="v1"),
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        module = container.store.authenticate_module(module_id, _bearer_token(authorization))
        if protocol_version != "v1":
            raise ValueError(f"Unsupported module protocol version: {protocol_version}")
        return module_service.get_module_config(container, module)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except sqlite3.OperationalError as exc:
        if not is_sqlite_busy_error(exc):
            raise
        raise HTTPException(status_code=503, detail=module_service.MODULE_INGEST_BUSY_DETAIL) from exc


@router.post("/module/events/batch", status_code=status.HTTP_202_ACCEPTED)
async def module_events_batch(
    payload: EventBatchRequest,
    authorization: Optional[str] = Header(default=None),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return await module_service.ingest_module_events(
            container,
            payload.model_dump(),
            _bearer_token(authorization),
        )
    except module_service.ModuleStorageBusyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except module_service.ModuleIngestionBusyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/modules")
def admin_list_modules(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_MODULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return module_service.list_modules(container)
    except ValueError as exc:
        status_code = 503 if "temporarily unavailable" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/admin/modules")
def admin_create_module(
    payload: ModuleProvisioningRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_MODULES_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        result = module_service.create_managed_module(container, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_admin_action(
        container,
        session,
        action="modules.create",
        target_type="module",
        target_id=str(result["module"]["module_id"]),
        details={"module_name": payload.module_name, "inbound_tags": payload.inbound_tags},
    )
    return result


@router.get("/admin/modules/{module_id}")
def admin_get_module(
    module_id: str,
    _: dict[str, Any] = Depends(require_permission(PERMISSION_MODULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return module_service.get_module_detail(container, module_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/admin/modules/{module_id}")
def admin_update_module(
    module_id: str,
    payload: ModuleProvisioningRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_MODULES_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        result = module_service.update_module_detail(container, module_id, payload.model_dump())
    except ValueError as exc:
        status_code = 404 if "not registered" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    record_admin_action(
        container,
        session,
        action="modules.update",
        target_type="module",
        target_id=module_id,
        details={"module_name": payload.module_name, "inbound_tags": payload.inbound_tags},
    )
    return result


@router.post("/admin/modules/{module_id}/token/reveal")
def admin_reveal_module_token(
    module_id: str,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_MODULES_TOKEN_REVEAL, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        result = module_service.reveal_module_token(container, module_id)
    except ValueError as exc:
        status_code = 404 if "not registered" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    record_admin_action(
        container,
        session,
        action="modules.token_reveal",
        target_type="module",
        target_id=module_id,
        details={},
    )
    return result
