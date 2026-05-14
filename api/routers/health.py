from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_container


router = APIRouter(tags=["health"])


@router.get("/ready")
def ready(container=Depends(get_container)) -> dict[str, Any]:
    payload = container.store.get_readiness_status()
    if not payload.get("ready"):
        detail = payload.get("error") or "database or schema is not ready"
        if payload.get("missing_tables"):
            detail = f"missing required tables: {', '.join(payload['missing_tables'])}"
        raise HTTPException(status_code=503, detail=detail)
    return {"status": "ok", "backend": payload.get("backend"), "target": payload.get("target")}


@router.get("/health")
def health(container=Depends(get_container)) -> dict[str, Any]:
    return container.store.get_health_snapshot()
