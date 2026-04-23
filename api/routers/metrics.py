from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from mobguard_platform import ReadSnapshotUnavailableError

from ..dependencies import get_container, require_permission
from ..permissions import PERMISSION_QUALITY_READ


router = APIRouter(prefix="/admin", tags=["metrics"])


@router.get("/metrics/quality")
def get_quality(
    module_id: str | None = Query(default=None),
    _: dict[str, Any] = Depends(require_permission(PERMISSION_QUALITY_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return container.store.get_quality_metrics(module_id=module_id)


@router.get("/metrics/overview")
def get_overview(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_QUALITY_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    try:
        return container.store.get_overview_metrics()
    except ReadSnapshotUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Overview snapshot is temporarily unavailable ({exc.reason})",
        ) from exc
