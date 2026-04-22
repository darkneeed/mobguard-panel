from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_container, require_permission
from ..permissions import (
    PERMISSION_REVIEWS_READ,
    PERMISSION_REVIEWS_RECHECK,
    PERMISSION_REVIEWS_RESOLVE,
    PERMISSION_RULES_READ,
    PERMISSION_RULES_WRITE,
)
from ..schemas.reviews import ReviewRecheckRequest, ReviewResolutionRequest, RulesUpdateRequest
from ..services.admin_audit import record_admin_action
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
    _: dict[str, Any] = Depends(require_permission(PERMISSION_REVIEWS_READ)),
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


@router.post("/reviews/recheck")
async def recheck_reviews(
    body: ReviewRecheckRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_REVIEWS_RECHECK)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = await review_service.recheck_reviews(
        container,
        {
            "limit": body.limit,
            "module_id": body.module_id,
            "review_reason": body.review_reason,
        },
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
    )
    record_admin_action(
        container,
        session,
        action="reviews.recheck",
        target_type="review_batch",
        target_id=str(payload.get("count", 0)),
        details={
            "limit": body.limit,
            "module_id": body.module_id or "",
            "review_reason": body.review_reason or "",
            "summary": payload.get("summary", {}),
        },
    )
    return payload


@router.get("/reviews/{case_id}")
def get_review(
    case_id: int,
    _: dict[str, Any] = Depends(require_permission(PERMISSION_REVIEWS_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return review_service.get_review(container, case_id)


@router.post("/reviews/{case_id}/resolve")
def resolve_review(
    case_id: int,
    body: ReviewResolutionRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_REVIEWS_RESOLVE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = review_service.resolve_review(
        container.store,
        case_id,
        body.resolution,
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        body.note,
    )
    record_admin_action(
        container,
        session,
        action="reviews.resolve",
        target_type="review_case",
        target_id=str(case_id),
        details={"resolution": body.resolution, "note": body.note or ""},
    )
    return payload


@router.get("/rules")
def get_rules(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return review_service.get_rules(container.store)


@router.put("/rules")
def put_rules(
    body: RulesUpdateRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_WRITE, require_owner_totp=True)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = review_service.update_rules(
        container.store,
        body.rules,
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        expected_revision=body.revision,
        expected_updated_at=body.updated_at,
    )
    if review_service.provider_tuning_changed(body.rules):
        asyncio.run(
            review_service.recheck_provider_sensitive_reviews(
                container,
                session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
                session["telegram_id"],
            )
        )
    record_admin_action(
        container,
        session,
        action="rules.update",
        target_type="live_rules",
        target_id="1",
        details={
            "keys": sorted(body.rules.keys()) if isinstance(body.rules, dict) else [],
            "revision": body.revision,
            "updated_at": body.updated_at,
        },
    )
    return payload
