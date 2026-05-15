from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from mobguard_platform import ReadSnapshotUnavailableError

from ..dependencies import get_container, require_permission
from ..permissions import PERMISSION_QUALITY_READ
from ..services.automation_status import (
    build_automation_status,
    build_enforcement_summary,
)
from ..services.panel_server import collect_panel_server_snapshot


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
        payload = container.store.get_overview_metrics(fast_read=True)
        payload["automation_status"] = build_automation_status(container)
        payload["enforcement"] = build_enforcement_summary(container)
        payload["panel_server"] = collect_panel_server_snapshot()
        return payload
    except ReadSnapshotUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Overview snapshot is temporarily unavailable ({exc.reason})",
        ) from exc
