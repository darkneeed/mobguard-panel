from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..dependencies import get_container, get_session


router = APIRouter(prefix="/admin", tags=["metrics"])


@router.get("/metrics/quality")
def get_quality(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return container.store.get_quality_metrics()
