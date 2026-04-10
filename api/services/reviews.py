from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from mobguard_platform import validate_live_rules_patch


def list_reviews(store: Any, filters: dict[str, Any]) -> dict[str, Any]:
    try:
        return store.list_review_cases(filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def get_review(store: Any, case_id: int) -> dict[str, Any]:
    try:
        return store.get_review_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def resolve_review(store: Any, case_id: int, resolution: str, actor: str, actor_tg_id: int, note: str) -> dict[str, Any]:
    try:
        return store.resolve_review_case(case_id, resolution.upper(), actor, actor_tg_id, note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
