from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..dependencies import get_container


router = APIRouter(tags=["health"])


@router.get("/health")
def health(container=Depends(get_container)) -> dict[str, Any]:
    return container.store.get_health_snapshot()
