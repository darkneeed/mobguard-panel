from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from ..context import APIContainer


def list_overrides(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        unsure = []
        if container.store._table_exists(conn, "unsure_patterns"):
            unsure = conn.execute(
                """
                SELECT ip_pattern, decision, timestamp
                FROM unsure_patterns
                ORDER BY timestamp DESC
                """
            ).fetchall()
        exact_ip = conn.execute(
            """
            SELECT ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at
            FROM exact_ip_overrides
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return {"exact_ip": [dict(row) for row in exact_ip], "unsure_patterns": [dict(row) for row in unsure]}


def delete_exact_override(container: APIContainer, ip: str) -> dict[str, Any]:
    with container.store._connect() as conn:
        conn.execute("DELETE FROM exact_ip_overrides WHERE ip = ?", (ip,))
        conn.commit()
    return {"ok": True}


def upsert_unsure_override(container: APIContainer, ip: str, decision: str) -> dict[str, Any]:
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_patterns"):
            raise HTTPException(status_code=400, detail="unsure_patterns table is unavailable")
        conn.execute(
            """
            INSERT INTO unsure_patterns (ip_pattern, decision, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(ip_pattern) DO UPDATE SET decision = excluded.decision, timestamp = excluded.timestamp
            """,
            (ip, decision, now),
        )
        conn.commit()
    return {"ok": True, "ip": ip, "decision": decision}


def delete_unsure_override(container: APIContainer, ip: str) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_patterns"):
            return {"ok": True}
        conn.execute("DELETE FROM unsure_patterns WHERE ip_pattern = ?", (ip,))
        conn.commit()
    return {"ok": True}


def list_cache(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ip_decisions"):
            return {"items": []}
        rows = conn.execute(
            """
            SELECT ip, status, confidence, details, asn, expires, log_json, bundle_json
            FROM ip_decisions
            ORDER BY expires DESC
            LIMIT 200
            """
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


def patch_cache(container: APIContainer, ip: str, updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        raise HTTPException(status_code=400, detail="No cache fields provided")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ip_decisions"):
            raise HTTPException(status_code=400, detail="ip_decisions table is unavailable")
        conn.execute(f"UPDATE ip_decisions SET {assignments} WHERE ip = ?", [*updates.values(), ip])
        conn.commit()
        row = conn.execute(
            "SELECT ip, status, confidence, details, asn, expires, log_json, bundle_json FROM ip_decisions WHERE ip = ?",
            (ip,),
        ).fetchone()
    return dict(row) if row else {"ok": False}


def delete_cache(container: APIContainer, ip: str) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ip_decisions"):
            return {"ok": True}
        conn.execute("DELETE FROM ip_decisions WHERE ip = ?", (ip,))
        conn.commit()
    return {"ok": True}
