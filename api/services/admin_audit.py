from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from ..context import APIContainer
from mobguard_platform.storage.sqlite import is_sqlite_busy_error, run_with_sqlite_retry


logger = logging.getLogger(__name__)
ADMIN_AUDIT_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2)


def actor_name(session: dict[str, Any]) -> str:
    return (
        str(session.get("username") or "").strip()
        or str(session.get("first_name") or "").strip()
        or str(session.get("subject") or "").strip()
        or f"tg:{int(session.get('telegram_id') or 0)}"
    )


def record_admin_action(
    container: APIContainer,
    session: dict[str, Any],
    *,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "actor_subject": str(session.get("subject") or ""),
        "actor_role": str(session.get("role") or "viewer"),
        "actor_auth_method": str(session.get("auth_method") or "unknown"),
        "actor_telegram_id": int(session.get("telegram_id") or 0) or None,
        "actor_username": actor_name(session),
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
    }
    try:
        return run_with_sqlite_retry(
            lambda: container.store.record_admin_audit_event(**payload),
            retry_delays_seconds=ADMIN_AUDIT_RETRY_DELAYS_SECONDS,
        )
    except sqlite3.OperationalError as exc:
        if not is_sqlite_busy_error(exc):
            raise
        logger.warning(
            "Admin audit skipped because SQLite is busy: action=%s target=%s:%s",
            action,
            target_type,
            target_id,
        )
        return {
            "id": 0,
            **payload,
            "created_at": datetime.utcnow().replace(microsecond=0).isoformat(),
            "persisted": False,
            "skip_reason": "database_locked",
        }
