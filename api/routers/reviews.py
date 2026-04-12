from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_container, get_session
from ..schemas.reviews import ReviewResolutionRequest, RulesUpdateRequest
from ..services import reviews as review_service


router = APIRouter(prefix="/admin", tags=["reviews"])


@router.get("/reviews")
def list_reviews(
    status: Optional[str] = None,
    confidence_band: Optional[str] = None,
    review_reason: Optional[str] = None,
    severity: Optional[str] = None,
    punitive_eligible: Optional[bool] = None,
    asn: Optional[int] = None,
    module_id: Optional[str] = None,
    q: Optional[str] = None,
    username: Optional[str] = None,
    system_id: Optional[int] = None,
    telegram_id: Optional[str] = None,
    opened_from: Optional[str] = None,
    opened_to: Optional[str] = None,
    repeat_count_min: Optional[int] = None,
    repeat_count_max: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort: str = Query(default="updated_desc"),
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return review_service.list_reviews(
        container,
        {
            "status": status,
            "confidence_band": confidence_band,
            "review_reason": review_reason,
            "severity": severity,
            "punitive_eligible": punitive_eligible,
            "asn": asn,
            "module_id": module_id,
            "q": q,
            "username": username,
            "system_id": system_id,
            "telegram_id": telegram_id,
            "opened_from": opened_from,
            "opened_to": opened_to,
            "repeat_count_min": repeat_count_min,
            "repeat_count_max": repeat_count_max,
            "page": page,
            "page_size": page_size,
            "sort": sort,
        },
    )


@router.get("/reviews/{case_id}")
def get_review(case_id: int, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return review_service.get_review(container, case_id)


@router.post("/reviews/{case_id}/resolve")
def resolve_review(
    case_id: int,
    body: ReviewResolutionRequest,
    session: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return review_service.resolve_review(
        container.store,
        case_id,
        body.resolution,
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        body.note,
    )


@router.get("/rules")
def get_rules(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return review_service.get_rules(container.store)


@router.put("/rules")
def put_rules(
    payload: RulesUpdateRequest,
    session: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return review_service.update_rules(
        container.store,
        payload.rules,
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        expected_revision=payload.revision,
        expected_updated_at=payload.updated_at,
    )
