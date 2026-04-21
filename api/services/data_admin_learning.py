from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..context import APIContainer


def get_learning_admin(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_learning"):
            return {
                "promoted_active": [],
                "promoted_stats": [],
                "legacy": [],
                "promoted_provider_active": [],
                "promoted_provider_service_active": [],
                "promoted_provider_stats": [],
                "promoted_provider_service_stats": [],
                "legacy_provider": [],
                "legacy_provider_service": [],
            }
        promoted_active = conn.execute(
            """
            SELECT pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
            FROM learning_patterns_active
            ORDER BY support DESC, precision DESC
            LIMIT 200
            """
        ).fetchall()
        promoted_stats = conn.execute(
            """
            SELECT pattern_type, pattern_value, decision, support, total, precision, updated_at, metadata_json
            FROM learning_pattern_stats
            ORDER BY total DESC, precision DESC
            LIMIT 200
            """
        ).fetchall()
        legacy = conn.execute(
            """
            SELECT id, pattern_type, pattern_value, decision, confidence, timestamp
            FROM unsure_learning
            ORDER BY confidence DESC, timestamp DESC
            LIMIT 200
            """
        ).fetchall()
    promoted_active_rows = [dict(row) for row in promoted_active]
    promoted_stats_rows = [dict(row) for row in promoted_stats]
    legacy_rows = [dict(row) for row in legacy]
    return {
        "promoted_active": promoted_active_rows,
        "promoted_stats": promoted_stats_rows,
        "legacy": legacy_rows,
        "promoted_provider_active": [
            row for row in promoted_active_rows if row.get("pattern_type") == "provider"
        ],
        "promoted_provider_service_active": [
            row for row in promoted_active_rows if row.get("pattern_type") == "provider_service"
        ],
        "promoted_provider_stats": [
            row for row in promoted_stats_rows if row.get("pattern_type") == "provider"
        ],
        "promoted_provider_service_stats": [
            row for row in promoted_stats_rows if row.get("pattern_type") == "provider_service"
        ],
        "legacy_provider": [row for row in legacy_rows if row.get("pattern_type") == "provider"],
        "legacy_provider_service": [
            row for row in legacy_rows if row.get("pattern_type") == "provider_service"
        ],
    }


def patch_legacy_learning(container: APIContainer, row_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        raise HTTPException(status_code=400, detail="No legacy learning fields provided")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_learning"):
            raise HTTPException(status_code=400, detail="unsure_learning table is unavailable")
        conn.execute(f"UPDATE unsure_learning SET {assignments} WHERE id = ?", [*updates.values(), row_id])
        conn.commit()
        row = conn.execute(
            "SELECT id, pattern_type, pattern_value, decision, confidence, timestamp FROM unsure_learning WHERE id = ?",
            (row_id,),
        ).fetchone()
    return dict(row) if row else {"ok": False}


def delete_legacy_learning(container: APIContainer, row_id: int) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_learning"):
            return {"ok": True}
        conn.execute("DELETE FROM unsure_learning WHERE id = ?", (row_id,))
        conn.commit()
    return {"ok": True}
