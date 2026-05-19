from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..dependencies import get_container, require_permission
from ..permissions import PERMISSION_DATA_READ, PERMISSION_DATA_WRITE
from ..services import bedolaga as bedolaga_service


router = APIRouter(prefix="/admin/bedolaga", tags=["bedolaga"])


class BedolagaActionRequest(BaseModel):
    path: str = Field(min_length=1)
    method: str = Field(default="POST")
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/overview")
def get_bedolaga_overview(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return bedolaga_service.get_bedolaga_overview(container)


@router.post("/action")
def post_bedolaga_action(
    body: BedolagaActionRequest,
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return bedolaga_service.proxy_bedolaga_action(
        container,
        path=body.path,
        method=body.method,
        payload=body.payload,
    )
