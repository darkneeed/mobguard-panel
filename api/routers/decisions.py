from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_container, require_permission
from ..permissions import PERMISSION_DATA_READ
from ..services import decisions as decisions_service


router = APIRouter(prefix="/admin", tags=["decisions"])


@router.get("/decisions/auto")
def list_auto_decisions(
    module_id: Optional[str] = None,
    provider: Optional[str] = None,
    verdict: Optional[str] = None,
    decision_source: Optional[str] = None,
    enforcement_status: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="created_desc"),
    compact: bool = Query(default=False),
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return decisions_service.list_decisions_auto(
        container,
        {
            "module_id": module_id,
            "provider": provider,
            "verdict": verdict,
            "decision_source": decision_source,
            "enforcement_status": enforcement_status,
            "q": q,
            "page": page,
            "page_size": page_size,
            "sort": sort,
            "compact": compact,
        },
    )
