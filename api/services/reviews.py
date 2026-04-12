from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from mobguard_platform import validate_live_rules_patch
from .runtime_state import panel_client


def _needs_identity_backfill(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) in (None, "") for key in ("uuid", "username", "telegram_id"))


def _lookup_identifier(payload: dict[str, Any]) -> str:
    for key in ("system_id", "telegram_id", "uuid", "username"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _persist_review_identity(store: Any, case_id: int, latest_event_id: int | None, user: dict[str, Any]) -> None:
    uuid = str(user.get("uuid") or "").strip() or None
    username = str(user.get("username") or "").strip() or None
    system_id = user.get("id")
    try:
        normalized_system_id = int(system_id) if system_id is not None else None
    except (TypeError, ValueError):
        normalized_system_id = None
    telegram_id = user.get("telegramId")
    normalized_telegram_id = str(telegram_id).strip() if telegram_id not in (None, "") else None

    with store._connect() as conn:
        conn.execute(
            """
            UPDATE review_cases
            SET uuid = ?, username = ?, system_id = ?, telegram_id = ?
            WHERE id = ?
            """,
            (uuid, username, normalized_system_id, normalized_telegram_id, case_id),
        )
        if latest_event_id is not None:
            conn.execute(
                """
                UPDATE analysis_events
                SET uuid = ?, username = ?, system_id = ?, telegram_id = ?
                WHERE id = ?
                """,
                (uuid, username, normalized_system_id, normalized_telegram_id, latest_event_id),
            )
        conn.commit()


def _backfill_review_case_identity(container: Any, case_id: int) -> bool:
    with container.store._connect() as conn:
        row = conn.execute(
            """
            SELECT id, latest_event_id, uuid, username, system_id, telegram_id
            FROM review_cases
            WHERE id = ?
            """,
            (case_id,),
        ).fetchone()
    if not row:
        return False

    payload = dict(row)
    if not _needs_identity_backfill(payload):
        return False

    identifier = _lookup_identifier(payload)
    if not identifier:
        return False

    user = panel_client(container).get_user_data(identifier)
    if not user:
        return False

    _persist_review_identity(container.store, int(payload["id"]), payload.get("latest_event_id"), user)
    return True


def list_reviews(container: Any, filters: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = container.store.list_review_cases(filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    refreshed = False
    for item in payload.get("items", []):
        if _backfill_review_case_identity(container, int(item["id"])):
            refreshed = True
    return container.store.list_review_cases(filters) if refreshed else payload


def get_review(container: Any, case_id: int) -> dict[str, Any]:
    try:
        _backfill_review_case_identity(container, case_id)
        return container.store.get_review_case(case_id)
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
