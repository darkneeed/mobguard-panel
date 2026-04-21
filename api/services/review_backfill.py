from __future__ import annotations

from typing import Any

from .runtime_state import panel_client


def _needs_identity_backfill(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) in (None, "") for key in ("uuid", "username", "telegram_id"))


def _lookup_identifier(payload: dict[str, Any]) -> str:
    for key in ("system_id", "telegram_id", "uuid", "username"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _persist_review_identity(conn: Any, case_id: int, latest_event_id: int | None, user: dict[str, Any]) -> None:
    uuid = str(user.get("uuid") or "").strip() or None
    username = str(user.get("username") or "").strip() or None
    system_id = user.get("id")
    try:
        normalized_system_id = int(system_id) if system_id is not None else None
    except (TypeError, ValueError):
        normalized_system_id = None
    telegram_id = user.get("telegramId")
    normalized_telegram_id = str(telegram_id).strip() if telegram_id not in (None, "") else None

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


def backfill_review_case_identities(
    container: Any,
    case_ids: list[int],
    *,
    max_remote_lookups: int = 50,
) -> bool:
    normalized_case_ids = sorted({int(case_id) for case_id in case_ids if int(case_id) > 0})
    if not normalized_case_ids:
        return False

    placeholders = ", ".join("?" for _ in normalized_case_ids)
    with container.store._connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, latest_event_id, uuid, username, system_id, telegram_id
            FROM review_cases
            WHERE id IN ({placeholders})
            """,
            tuple(normalized_case_ids),
        ).fetchall()

    pending_by_identifier: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        payload = dict(row)
        if not _needs_identity_backfill(payload):
            continue
        identifier = _lookup_identifier(payload)
        if not identifier:
            continue
        pending_by_identifier.setdefault(identifier, []).append(payload)

    if not pending_by_identifier:
        return False

    client = panel_client(container)
    fetched_users: dict[str, dict[str, Any]] = {}
    for identifier in list(pending_by_identifier.keys())[: max(int(max_remote_lookups), 1)]:
        user = client.get_user_data(identifier)
        if user:
            fetched_users[identifier] = user

    if not fetched_users:
        return False

    updated = False
    with container.store._connect() as conn:
        for identifier, payloads in pending_by_identifier.items():
            user = fetched_users.get(identifier)
            if not user:
                continue
            for payload in payloads:
                _persist_review_identity(
                    conn,
                    int(payload["id"]),
                    int(payload["latest_event_id"]) if payload.get("latest_event_id") is not None else None,
                    user,
                )
                updated = True
        if updated:
            conn.commit()
    return updated
