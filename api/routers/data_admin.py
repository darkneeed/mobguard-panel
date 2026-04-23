from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response

from ..dependencies import get_container, require_permission
from ..permissions import PERMISSION_AUDIT_READ, PERMISSION_DATA_READ, PERMISSION_DATA_WRITE
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
from ..services.admin_audit import record_admin_action
from ..services import data_admin as data_service
from ..services import reviews as review_service


router = APIRouter(prefix="/admin/data", tags=["data-admin"])


@router.get("/users/search")
def search_users(
    query: str = Query(min_length=1),
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.search_users(container, query)


@router.get("/users/{identifier}")
def get_user_card(
    identifier: str,
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.get_user_card(container, identifier)


@router.get("/users/{identifier}/export")
def export_user_card(
    identifier: str,
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.get_user_card_export(container, identifier)


@router.post("/users/{identifier}/ban")
def ban_user(
    identifier: str,
    body: UserBanRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.ban_user(container, identifier, body.minutes)
    record_admin_action(
        container,
        session,
        action="data.user.ban",
        target_type="user",
        target_id=identifier,
        details={"minutes": body.minutes},
    )
    return payload


@router.post("/users/{identifier}/unban")
def unban_user(
    identifier: str,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.unban_user(container, identifier)
    record_admin_action(
        container,
        session,
        action="data.user.unban",
        target_type="user",
        target_id=identifier,
        details={},
    )
    return payload


@router.post("/users/{identifier}/traffic-cap")
def apply_user_traffic_cap(
    identifier: str,
    body: UserTrafficCapRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.apply_user_traffic_cap(container, identifier, body.gigabytes)
    record_admin_action(
        container,
        session,
        action="data.user.traffic_cap.apply",
        target_type="user",
        target_id=identifier,
        details={"gigabytes": body.gigabytes},
    )
    return payload


@router.post("/users/{identifier}/traffic-cap/restore")
def restore_user_traffic_cap(
    identifier: str,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.restore_user_traffic_cap(container, identifier)
    record_admin_action(
        container,
        session,
        action="data.user.traffic_cap.restore",
        target_type="user",
        target_id=identifier,
        details={},
    )
    return payload


@router.post("/users/{identifier}/warnings")
def update_user_warnings(
    identifier: str,
    body: UserWarningsRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.update_user_warnings(container, identifier, body.action.lower(), body.count)
    record_admin_action(
        container,
        session,
        action="data.user.warnings",
        target_type="user",
        target_id=identifier,
        details={"action": body.action.lower(), "count": body.count},
    )
    return payload


@router.post("/users/{identifier}/strikes")
def update_user_strikes(
    identifier: str,
    body: UserStrikesRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.update_user_strikes(container, identifier, body.action.lower(), body.count)
    record_admin_action(
        container,
        session,
        action="data.user.strikes",
        target_type="user",
        target_id=identifier,
        details={"action": body.action.lower(), "count": body.count},
    )
    return payload


@router.post("/users/{identifier}/exempt")
def update_user_exemptions(
    identifier: str,
    body: UserExemptRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.update_user_exemptions(container, identifier, body.kind.lower(), body.enabled, session)
    record_admin_action(
        container,
        session,
        action="data.user.exemptions",
        target_type="user",
        target_id=identifier,
        details={"kind": body.kind.lower(), "enabled": bool(body.enabled)},
    )
    return payload


@router.get("/violations")
def list_violations(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.list_violations(container)


@router.get("/overrides")
def list_overrides(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.list_overrides(container)


@router.put("/overrides/ip/{ip}")
def upsert_exact_ip_override(
    ip: str,
    body: OverrideUpsertRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
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
    record_admin_action(
        container,
        session,
        action="data.overrides.exact.upsert",
        target_type="ip_override",
        target_id=ip,
        details={"decision": body.decision.upper(), "ttl_days": body.ttl_days},
    )
    return {"ok": True, "ip": ip, "decision": body.decision.upper()}


@router.delete("/overrides/ip/{ip}")
def delete_exact_ip_override(
    ip: str,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.delete_exact_override(container, ip)
    record_admin_action(
        container,
        session,
        action="data.overrides.exact.delete",
        target_type="ip_override",
        target_id=ip,
        details={},
    )
    return payload


@router.put("/overrides/unsure/{ip}")
def upsert_unsure_override(
    ip: str,
    body: OverrideUpsertRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.upsert_unsure_override(container, ip, body.decision.upper())
    record_admin_action(
        container,
        session,
        action="data.overrides.unsure.upsert",
        target_type="unsure_override",
        target_id=ip,
        details={"decision": body.decision.upper()},
    )
    return payload


@router.delete("/overrides/unsure/{ip}")
def delete_unsure_override(
    ip: str,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.delete_unsure_override(container, ip)
    record_admin_action(
        container,
        session,
        action="data.overrides.unsure.delete",
        target_type="unsure_override",
        target_id=ip,
        details={},
    )
    return payload


@router.get("/cache")
def list_cache(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.list_cache(container)


@router.patch("/cache/{ip}")
def patch_cache(
    ip: str,
    body: CachePatchRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    payload = data_service.patch_cache(container, ip, changes)
    record_admin_action(
        container,
        session,
        action="data.cache.patch",
        target_type="cache_entry",
        target_id=ip,
        details={"fields": sorted(changes.keys())},
    )
    return payload


@router.delete("/cache/{ip}")
def delete_cache(
    ip: str,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.delete_cache(container, ip)
    record_admin_action(
        container,
        session,
        action="data.cache.delete",
        target_type="cache_entry",
        target_id=ip,
        details={},
    )
    return payload


@router.get("/exports/calibration")
def export_calibration(
    opened_from: Optional[str] = None,
    opened_to: Optional[str] = None,
    review_reason: Optional[str] = None,
    provider_key: Optional[str] = None,
    include_unknown: bool = False,
    status: str = Query(default="resolved_only"),
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
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


@router.get("/exports/calibration/preview")
def preview_calibration_export(
    opened_from: Optional[str] = None,
    opened_to: Optional[str] = None,
    review_reason: Optional[str] = None,
    provider_key: Optional[str] = None,
    include_unknown: bool = False,
    status: str = Query(default="resolved_only"),
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.build_calibration_preview(
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


@router.get("/learning")
def get_learning_admin(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.get_learning_admin(container)


@router.patch("/learning/legacy/{row_id}")
def patch_legacy_learning(
    row_id: int,
    body: LegacyLearningPatchRequest,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    payload = data_service.patch_legacy_learning(container, row_id, changes)
    record_admin_action(
        container,
        session,
        action="data.learning.patch",
        target_type="legacy_learning",
        target_id=str(row_id),
        details={"fields": sorted(changes.keys())},
    )
    return payload


@router.delete("/learning/legacy/{row_id}")
def delete_legacy_learning(
    row_id: int,
    session: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_WRITE)),
    container=Depends(get_container),
) -> dict[str, Any]:
    payload = data_service.delete_legacy_learning(container, row_id)
    record_admin_action(
        container,
        session,
        action="data.learning.delete",
        target_type="legacy_learning",
        target_id=str(row_id),
        details={},
    )
    return payload


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
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
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


@router.get("/events")
def list_analysis_events(
    ip: Optional[str] = None,
    device_id: Optional[str] = None,
    module_id: Optional[str] = None,
    tag: Optional[str] = None,
    provider: Optional[str] = None,
    asn: Optional[int] = None,
    verdict: Optional[str] = None,
    confidence_band: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    has_review_case: Optional[bool] = None,
    q: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="created_desc"),
    _: dict[str, Any] = Depends(require_permission(PERMISSION_DATA_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.list_analysis_events(
        container,
        {
            "ip": ip,
            "device_id": device_id,
            "module_id": module_id,
            "tag": tag,
            "provider": provider,
            "asn": asn,
            "verdict": verdict,
            "confidence_band": confidence_band,
            "created_from": created_from,
            "created_to": created_to,
            "has_review_case": has_review_case,
            "q": q,
            "page": page,
            "page_size": page_size,
            "sort": sort,
        },
    )


@router.get("/audit")
def list_audit(
    limit: int = Query(default=100, ge=1, le=500),
    _: dict[str, Any] = Depends(require_permission(PERMISSION_AUDIT_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    return data_service.list_admin_audit(container, limit=limit)
