from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import HTTPException

from mobguard_platform import review_reason_for_bundle, validate_live_rules_patch
from mobguard_platform.usage_profile import build_usage_profile_snapshot

from .modules import _analyze_event, _build_batch_context
from .review_backfill import backfill_review_case_identities
from .runtime_state import enrich_panel_user_usage_context, panel_client


def list_reviews(container: Any, filters: dict[str, Any]) -> dict[str, Any]:
    try:
        return container.store.list_review_cases(filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def get_review(container: Any, case_id: int) -> dict[str, Any]:
    try:
        backfill_review_case_identities(container, [case_id], max_remote_lookups=1)
        payload = container.store.get_review_case(case_id)
        identity = {
            "uuid": payload.get("uuid"),
            "username": payload.get("username"),
            "system_id": payload.get("system_id"),
            "telegram_id": payload.get("telegram_id"),
        }
        remote_user = None
        client = panel_client(container)
        for candidate in (
            identity.get("uuid"),
            identity.get("system_id"),
            identity.get("telegram_id"),
            identity.get("username"),
        ):
            if candidate in (None, ""):
                continue
            remote_user = enrich_panel_user_usage_context(client, client.get_user_data(str(candidate)))
            if remote_user:
                break
        payload["usage_profile"] = build_usage_profile_snapshot(
            container.store,
            identity,
            panel_user=remote_user,
            anchor_started_at=payload.get("opened_at"),
            device_scope_key=str(payload.get("device_scope_key") or ""),
            case_scope_key=str(payload.get("case_scope_key") or ""),
        )
        return payload
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def resolve_review(store: Any, case_id: int, resolution: str, actor: str, actor_tg_id: int, note: str) -> dict[str, Any]:
    try:
        return store.resolve_review_case(case_id, resolution.upper(), actor, actor_tg_id, note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def recheck_reviews(
    container: Any,
    filters: dict[str, Any],
    actor: str,
    actor_tg_id: int,
) -> dict[str, Any]:
    try:
        limit = min(max(int(filters.get("limit", 100) or 100), 1), 500)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="limit must be an integer between 1 and 500") from exc

    review_filters = {
        "status": "OPEN",
        "page": 1,
        "page_size": limit,
        "sort": "updated_desc",
    }
    if filters.get("module_id"):
        review_filters["module_id"] = filters["module_id"]
    if filters.get("review_reason"):
        review_filters["review_reason"] = filters["review_reason"]

    listing = list_reviews(container, review_filters)
    case_ids = [int(item["id"]) for item in listing.get("items", [])]
    return await _recheck_case_ids(container, case_ids, actor, actor_tg_id)


async def _recheck_case_ids(
    container: Any,
    case_ids: list[int],
    actor: str,
    actor_tg_id: int,
) -> dict[str, Any]:
    rules_state = container.store.get_live_rules_state()
    revision = int(rules_state.get("revision") or 0)
    scoring_runtime = _build_batch_context(
        container,
        {"module_id": "review-recheck", "module_name": "review-recheck"},
    )

    changed_counts: Counter[str] = Counter()
    items: list[dict[str, Any]] = []
    for case_id in case_ids:
        detail = container.store.get_review_case(case_id)
        user_data = {
            "uuid": detail.get("uuid"),
            "username": detail.get("username"),
            "id": detail.get("system_id"),
            "telegramId": detail.get("telegram_id"),
            "module_id": detail.get("module_id"),
            "module_name": detail.get("module_name"),
        }
        payload = {
            "uuid": detail.get("uuid"),
            "username": detail.get("username"),
            "system_id": detail.get("system_id"),
            "telegram_id": detail.get("telegram_id"),
            "ip": detail.get("ip"),
            "tag": detail.get("tag"),
        }
        bundle = await _analyze_event(
            scoring_runtime,
            user_data,
            payload,
            persist_behavior_state=False,
            persist_decision=False,
        )
        next_review_reason = review_reason_for_bundle(bundle)
        auto_note = (
            f"auto recheck via live rules revision {revision}: "
            f"{bundle.verdict}/{bundle.confidence_band} score={bundle.score}"
        )
        updated = await container.store.async_recheck_review_case(
            case_id,
            user_data,
            str(detail.get("ip") or ""),
            str(detail.get("tag") or ""),
            bundle,
            next_review_reason,
            actor,
            actor_tg_id,
            auto_note,
        )
        if updated["status"] == "SKIPPED":
            changed_counts["closed"] += 1
        else:
            changed_counts["open"] += 1
        if str(detail.get("review_reason") or "") != str(updated.get("review_reason") or ""):
            changed_counts["reason_changed"] += 1
        if str(detail.get("verdict") or "") != str(updated.get("verdict") or ""):
            changed_counts["verdict_changed"] += 1
        if str(detail.get("confidence_band") or "") != str(updated.get("confidence_band") or ""):
            changed_counts["confidence_changed"] += 1
        if int(detail.get("score") or 0) != int(updated.get("score") or 0):
            changed_counts["score_changed"] += 1
        changed_counts["processed"] += 1
        items.append(
            {
                "id": updated["id"],
                "status": updated["status"],
                "review_reason": updated["review_reason"],
                "verdict": updated["verdict"],
                "confidence_band": updated["confidence_band"],
                "score": updated["score"],
                "ip": updated["ip"],
                "module_id": updated.get("module_id"),
            }
        )

    return {
        "items": items,
        "summary": dict(changed_counts),
        "revision": revision,
        "count": len(items),
    }


def provider_tuning_changed(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if "provider_profiles" in payload:
        return True
    settings = payload.get("settings")
    if not isinstance(settings, dict):
        return False
    return any(
        key in settings
        for key in (
            "provider_conflict_review_only",
            "provider_mobile_marker_bonus",
            "provider_home_marker_penalty",
        )
    )


async def recheck_provider_sensitive_reviews(
    container: Any,
    actor: str,
    actor_tg_id: int,
) -> dict[str, Any]:
    case_ids: list[int] = []
    for review_reason in ("unsure", "provider_conflict"):
        page = 1
        while True:
            listing = container.store.list_review_cases(
                {
                    "status": "OPEN",
                    "review_reason": review_reason,
                    "page": page,
                    "page_size": 100,
                    "sort": "updated_desc",
                }
            )
            batch_ids = [int(item["id"]) for item in listing.get("items", [])]
            case_ids.extend(batch_ids)
            if not batch_ids or page * int(listing.get("page_size") or 100) >= int(listing.get("count") or 0):
                break
            page += 1
    deduped_case_ids = sorted(set(case_ids))
    return await _recheck_case_ids(container, deduped_case_ids, actor, actor_tg_id)


def get_rules(store: Any) -> dict[str, Any]:
    return store.get_live_rules_state()


def update_rules(
    store: Any,
    payload: dict[str, Any],
    actor: str,
    actor_tg_id: int,
    *,
    expected_revision: int | None = None,
    expected_updated_at: str | None = None,
) -> dict[str, Any]:
    try:
        validate_live_rules_patch(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return store.update_live_rules(
            payload,
            actor,
            actor_tg_id,
            expected_revision=expected_revision,
            expected_updated_at=expected_updated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
