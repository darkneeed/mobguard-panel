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
                   confidence, reasoning_ru, operator_errors_json, suggested_provider_profile_json, status, created_at, updated_at
            FROM ai_learning_suggestions
            WHERE NOT (
                status = 'PENDING'
                AND current_decision = suggested_decision
                AND (operator_errors_json IS NULL OR operator_errors_json = '[]')
                AND (suggested_provider_profile_json IS NULL)
            )
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]

def accept_suggestion(container: APIContainer, suggestion_id: int) -> dict[str, Any]:
    reopened_cases = []
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
            "DELETE FROM ai_learning_suggestions WHERE pattern_type = ? AND pattern_value = ? AND status = 'ACCEPTED'",
            (row["pattern_type"], row["pattern_value"])
        )
        conn.execute(
            "UPDATE ai_learning_suggestions SET status = 'ACCEPTED', updated_at = ? WHERE id = ?",
            (now, suggestion_id)
        )
        
        # 2. Add/replace in learning_patterns_active
        conn.execute(
            """
            INSERT INTO learning_patterns_active (
                pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pattern_type, pattern_value) DO UPDATE SET
                decision = excluded.decision,
                support = excluded.support,
                precision = excluded.precision,
                promoted_at = excluded.promoted_at,
                metadata_json = excluded.metadata_json
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
        
    # 2b. Add/Update Operator Profile in live rules if suggested (run outside db lock)
    suggested_profile_json = row["suggested_provider_profile_json"]
    if suggested_profile_json:
        try:
            suggested_profile = json.loads(suggested_profile_json)
            if isinstance(suggested_profile, dict) and suggested_profile.get("key"):
                current_rules_state = container.store.get_live_rules_state()
                current_rules = current_rules_state.get("rules", {})
                current_profiles = list(current_rules.get("provider_profiles", []))
                
                updated_profiles = []
                found = False
                for prof in current_profiles:
                    if prof.get("key") == suggested_profile["key"]:
                        updated_profiles.append(suggested_profile)
                        found = True
                    else:
                        updated_profiles.append(prof)
                if not found:
                    updated_profiles.append(suggested_profile)
                    
                container.store.update_live_rules(
                    {"provider_profiles": updated_profiles},
                    "AI Auto-Learning Suggestions",
                    None
                )
        except Exception as e:
            # Keep executing reopened cases even if profile saving encounters validation/parsing errors
            pass
            
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
            "DELETE FROM ai_learning_suggestions WHERE pattern_type = ? AND pattern_value = ? AND status = 'REJECTED'",
            (row["pattern_type"], row["pattern_value"])
        )
        conn.execute(
            "UPDATE ai_learning_suggestions SET status = 'REJECTED', updated_at = ? WHERE id = ?",
            (now, suggestion_id)
        )
        conn.commit()
        
    return {"success": True, "suggestion_id": suggestion_id}


def get_suggestions_cooldown_status(container: APIContainer) -> dict[str, Any]:
    last_run_str = container.store.get_metadata_value("last_ai_suggestions_timestamp")
    cooldown_hours = 12
    cooldown_seconds = cooldown_hours * 3600
    if not last_run_str:
        return {
            "last_run": None,
            "cooldown_seconds": cooldown_seconds,
            "seconds_remaining": 0,
            "can_run": True
        }
    try:
        last_run = datetime.fromisoformat(last_run_str)
        elapsed = (datetime.utcnow() - last_run).total_seconds()
        seconds_remaining = max(0, int(cooldown_seconds - elapsed))
        return {
            "last_run": last_run_str,
            "cooldown_seconds": cooldown_seconds,
            "seconds_remaining": seconds_remaining,
            "can_run": seconds_remaining <= 0
        }
    except Exception:
        return {
            "last_run": None,
            "cooldown_seconds": cooldown_seconds,
            "seconds_remaining": 0,
            "can_run": True
        }


def generate_suggestions_on_demand(container: APIContainer, session: dict[str, Any], force: bool = False) -> dict[str, Any]:
    status = get_suggestions_cooldown_status(container)
    if not status["can_run"] and not force:
        raise HTTPException(status_code=400, detail=f"Cooldown in effect. Please wait {status['seconds_remaining']} seconds.")
    
    settings = container.runtime.config.get("settings", {})
    api_key = settings.get("gemini_api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API key is not configured. Please enter your API Key in System > Integrations.")

    from scripts.ai_learning_cron import run_ai_audit
    run_ai_audit(container.runtime, container.store)
    
    return {
        "success": True,
        "suggestions": get_suggestions(container)
    }
