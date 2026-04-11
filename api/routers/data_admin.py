from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response

from ..dependencies import get_container, get_session
from ..schemas.data_admin import (
    CachePatchRequest,
    LegacyLearningPatchRequest,
    OverrideUpsertRequest,
    UserBanRequest,
    UserExemptRequest,
    UserTrafficCapRequest,
    UserStrikesRequest,
    UserWarningsRequest,
)
from ..services import data_admin as data_service
from ..services import reviews as review_service


router = APIRouter(prefix="/admin/data", tags=["data-admin"])


@router.get("/users/search")
def search_users(query: str = Query(min_length=1), _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.search_users(container, query)


@router.get("/users/{identifier}")
def get_user_card(identifier: str, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.get_user_card(container, identifier)


@router.get("/users/{identifier}/export")
def export_user_card(identifier: str, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.get_user_card_export(container, identifier)


@router.post("/users/{identifier}/ban")
def ban_user(
    identifier: str,
    body: UserBanRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.ban_user(container, identifier, body.minutes)


@router.post("/users/{identifier}/unban")
def unban_user(identifier: str, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.unban_user(container, identifier)


@router.post("/users/{identifier}/traffic-cap")
def apply_user_traffic_cap(
    identifier: str,
    body: UserTrafficCapRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.apply_user_traffic_cap(container, identifier, body.gigabytes)


@router.post("/users/{identifier}/traffic-cap/restore")
def restore_user_traffic_cap(
    identifier: str,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.restore_user_traffic_cap(container, identifier)


@router.post("/users/{identifier}/warnings")
def update_user_warnings(
    identifier: str,
    body: UserWarningsRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.update_user_warnings(container, identifier, body.action.lower(), body.count)


@router.post("/users/{identifier}/strikes")
def update_user_strikes(
    identifier: str,
    body: UserStrikesRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.update_user_strikes(container, identifier, body.action.lower(), body.count)


@router.post("/users/{identifier}/exempt")
def update_user_exemptions(
    identifier: str,
    body: UserExemptRequest,
    session: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.update_user_exemptions(container, identifier, body.kind.lower(), body.enabled, session)


@router.get("/violations")
def list_violations(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.list_violations(container)


@router.get("/overrides")
def list_overrides(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.list_overrides(container)


@router.put("/overrides/ip/{ip}")
def upsert_exact_ip_override(
    ip: str,
    body: OverrideUpsertRequest,
    session: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    container.store.set_ip_override(
        ip,
        body.decision.upper(),
        "data_admin",
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        ttl_days=body.ttl_days,
    )
    return {"ok": True, "ip": ip, "decision": body.decision.upper()}


@router.delete("/overrides/ip/{ip}")
def delete_exact_ip_override(ip: str, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.delete_exact_override(container, ip)


@router.put("/overrides/unsure/{ip}")
def upsert_unsure_override(
    ip: str,
    body: OverrideUpsertRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.upsert_unsure_override(container, ip, body.decision.upper())


@router.delete("/overrides/unsure/{ip}")
def delete_unsure_override(ip: str, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.delete_unsure_override(container, ip)


@router.get("/cache")
def list_cache(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.list_cache(container)


@router.patch("/cache/{ip}")
def patch_cache(
    ip: str,
    body: CachePatchRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.patch_cache(container, ip, {key: value for key, value in body.model_dump().items() if value is not None})


@router.delete("/cache/{ip}")
def delete_cache(ip: str, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.delete_cache(container, ip)


@router.get("/exports/calibration")
def export_calibration(
    opened_from: Optional[str] = None,
    opened_to: Optional[str] = None,
    review_reason: Optional[str] = None,
    provider_key: Optional[str] = None,
    include_unknown: bool = False,
    status: str = Query(default="resolved_only"),
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> Response:
    payload = data_service.build_calibration_export(
        container,
        {
            "opened_from": opened_from,
            "opened_to": opened_to,
            "review_reason": review_reason,
            "provider_key": provider_key,
            "include_unknown": include_unknown,
            "status": status,
        },
    )
    return Response(
        content=payload["content"],
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{payload["filename"]}"',
            "X-MobGuard-Export-Manifest": payload["manifest_header"],
        },
    )


@router.get("/learning")
def get_learning_admin(_: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.get_learning_admin(container)


@router.patch("/learning/legacy/{row_id}")
def patch_legacy_learning(
    row_id: int,
    body: LegacyLearningPatchRequest,
    _: dict[str, Any] = Depends(get_session),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.patch_legacy_learning(container, row_id, {key: value for key, value in body.model_dump().items() if value is not None})


@router.delete("/learning/legacy/{row_id}")
def delete_legacy_learning(row_id: int, _: dict[str, Any] = Depends(get_session), container=Depends(get_container)) -> dict[str, Any]:
    return data_service.delete_legacy_learning(container, row_id)


@router.get("/cases")
def list_cases(
    status: Optional[str] = None,
    confidence_band: Optional[str] = None,
    review_reason: Optional[str] = None,
    severity: Optional[str] = None,
    punitive_eligible: Optional[bool] = None,
    asn: Optional[int] = None,
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
        container.store,
        {
            "status": status,
            "confidence_band": confidence_band,
            "review_reason": review_reason,
            "severity": severity,
            "punitive_eligible": punitive_eligible,
            "asn": asn,
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
