from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from fastapi import HTTPException
from ..context import APIContainer

def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()

def get_suggestions(container: APIContainer) -> list[dict[str, Any]]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ai_learning_suggestions"):
            return []
        rows = conn.execute(
            """
            SELECT id, pattern_type, pattern_value, current_decision, suggested_decision,
                   confidence, reasoning_ru, operator_errors_json, status, created_at, updated_at
            FROM ai_learning_suggestions
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]

def accept_suggestion(container: APIContainer, suggestion_id: int) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ai_learning_suggestions"):
            raise HTTPException(status_code=400, detail="Table ai_learning_suggestions not found")
        
        row = conn.execute(
            "SELECT * FROM ai_learning_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Suggestion not found")
            
        if row["status"] != "PENDING":
            return {"success": False, "detail": f"Suggestion already {row['status']}"}
            
        now = _utcnow()
        # 1. Update suggestion status
        conn.execute(
            "UPDATE ai_learning_suggestions SET status = 'ACCEPTED', updated_at = ? WHERE id = ?",
            (now, suggestion_id)
        )
        
        # 2. Add/replace in learning_patterns_active
        conn.execute(
            """
            INSERT OR REPLACE INTO learning_patterns_active (
                pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["pattern_type"],
                row["pattern_value"],
                row["suggested_decision"],
                999,
                1.0,
                now,
                json.dumps({"ai_promoted": True, "reasoning": row["reasoning_ru"]}, ensure_ascii=False)
            )
        )
        
        # 3. Process operator errors: reopen those cases and mark/prioritize them
        errors_json = row["operator_errors_json"]
        reopened_cases = []
        if errors_json:
            try:
                case_ids = json.loads(errors_json)
                if isinstance(case_ids, list):
                    for cid in case_ids:
                        case_row = conn.execute(
                            "SELECT review_reason, usage_profile_priority FROM review_cases WHERE id = ?",
                            (int(cid),)
                        ).fetchone()
                        if case_row:
                            reason = case_row["review_reason"]
                            if not reason.startswith("[AI Recheck]"):
                                reason = f"[AI Recheck] {reason}"
                            priority = int(case_row["usage_profile_priority"] or 0)
                            if priority < 10000:
                                priority += 10000
                            
                            conn.execute(
                                """
                                UPDATE review_cases
                                SET status = 'OPEN',
                                    review_reason = ?,
                                    usage_profile_priority = ?,
                                    updated_at = ?
                                WHERE id = ?
                                """,
                                (reason, priority, now, int(cid))
                            )
                            reopened_cases.append(cid)
            except Exception as e:
                pass
                
        conn.commit()
        
    return {
        "success": True,
        "suggestion_id": suggestion_id,
        "reopened_cases": reopened_cases
    }

def reject_suggestion(container: APIContainer, suggestion_id: int) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ai_learning_suggestions"):
            raise HTTPException(status_code=400, detail="Table ai_learning_suggestions not found")
            
        row = conn.execute(
            "SELECT * FROM ai_learning_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Suggestion not found")
            
        if row["status"] != "PENDING":
            return {"success": False, "detail": f"Suggestion already {row['status']}"}
            
        now = _utcnow()
        conn.execute(
            "UPDATE ai_learning_suggestions SET status = 'REJECTED', updated_at = ? WHERE id = ?",
            (now, suggestion_id)
        )
        conn.commit()
        
    return {"success": True, "suggestion_id": suggestion_id}
