from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Any, Optional
from fastapi import HTTPException

from ..context import APIContainer
from .runtime_state import load_runtime_config, load_env_values

logger = logging.getLogger(__name__)

def get_ai_optimization_data(container: APIContainer) -> dict[str, Any]:
    live_state = container.store.get_live_rules_state()
    rules = live_state.get("rules", {})
    
    twenty_four_hours_ago = (datetime.utcnow() - timedelta(hours=24)).replace(microsecond=0).isoformat()
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).replace(microsecond=0).isoformat()
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).replace(microsecond=0).isoformat()

    with container.store._connect() as conn:
        # 1. 24h Stats
        row_stats = conn.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN verdict = 'MOBILE' THEN 1 ELSE 0 END) as mobile_count,
                SUM(CASE WHEN verdict = 'HOME' THEN 1 ELSE 0 END) as home_count,
                SUM(CASE WHEN verdict = 'UNSURE' THEN 1 ELSE 0 END) as unsure_count
            FROM analysis_events
            WHERE created_at >= ?
            """,
            (twenty_four_hours_ago,)
        ).fetchone()
        
        if row_stats:
            try:
                stats_24h = {
                    "total": int(row_stats["total"] or 0),
                    "mobile_count": int(row_stats["mobile_count"] or 0),
                    "home_count": int(row_stats["home_count"] or 0),
                    "unsure_count": int(row_stats["unsure_count"] or 0),
                }
            except Exception:
                stats_24h = {
                    "total": int(row_stats[0] or 0),
                    "mobile_count": int(row_stats[1] or 0),
                    "home_count": int(row_stats[2] or 0),
                    "unsure_count": int(row_stats[3] or 0),
                }
        else:
            stats_24h = {"total": 0, "mobile_count": 0, "home_count": 0, "unsure_count": 0}

        # 2. 7d Resolved Reviews (Reversals/Overrides)
        row_overrides = conn.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN verdict = 'MOBILE' THEN 1 ELSE 0 END) as resolved_mobile,
                SUM(CASE WHEN verdict = 'HOME' THEN 1 ELSE 0 END) as resolved_home
            FROM review_cases
            WHERE status = 'RESOLVED' AND updated_at >= ?
            """,
            (seven_days_ago,)
        ).fetchone()

        if row_overrides:
            try:
                overrides_7d = {
                    "total": int(row_overrides["total"] or 0),
                    "resolved_mobile": int(row_overrides["resolved_mobile"] or 0),
                    "resolved_home": int(row_overrides["resolved_home"] or 0),
                }
            except Exception:
                overrides_7d = {
                    "total": int(row_overrides[0] or 0),
                    "resolved_mobile": int(row_overrides[1] or 0),
                    "resolved_home": int(row_overrides[2] or 0),
                }
        else:
            overrides_7d = {"total": 0, "resolved_mobile": 0, "resolved_home": 0}

        # 3. Top 10 Unsure ASNs over last 3 days
        asn_rows = conn.execute(
            """
            SELECT asn, isp, COUNT(*) as count
            FROM analysis_events
            WHERE verdict = 'UNSURE' AND created_at >= ? AND asn IS NOT NULL
            GROUP BY asn, isp
            ORDER BY count DESC
            LIMIT 10
            """,
            (three_days_ago,)
        ).fetchall()
        
        top_unsure_asns = []
        for r in asn_rows:
            try:
                top_unsure_asns.append({
                    "asn": r["asn"],
                    "isp": r["isp"],
                    "count": r["count"]
                })
            except Exception:
                top_unsure_asns.append({
                    "asn": r[0],
                    "isp": r[1],
                    "count": r[2]
                })

        # 4. Recent UNSURE and HOME connection samples (strictly no user profile identifiers)
        recent_event_rows = conn.execute(
            """
            SELECT ip, asn, isp, score, verdict, created_at
            FROM analysis_events
            WHERE (verdict = 'UNSURE' OR verdict = 'HOME') AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (three_days_ago,)
        ).fetchall()

        recent_events = []
        for r in recent_event_rows:
            try:
                recent_events.append({
                    "ip": r["ip"],
                    "asn": r["asn"],
                    "isp": r["isp"],
                    "score": r["score"],
                    "verdict": r["verdict"],
                    "created_at": r["created_at"]
                })
            except Exception:
                recent_events.append({
                    "ip": r[0],
                    "asn": r[1],
                    "isp": r[2],
                    "score": r[3],
                    "verdict": r[4],
                    "created_at": r[5]
                })

    return {
        "rules": rules,
        "stats_24h": stats_24h,
        "overrides_7d": overrides_7d,
        "top_unsure_asns": top_unsure_asns,
        "recent_events": recent_events
    }

def get_optimizer_cooldown_status(container: APIContainer) -> dict[str, Any]:
    last_run_str = container.store.get_metadata_value("last_ai_optimizer_timestamp")
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

def generate_gemini_recommendations(container: APIContainer, force: bool = False) -> dict[str, Any]:
    # Check cooldown first
    if not force:
        status = get_optimizer_cooldown_status(container)
        if not status["can_run"]:
            raise HTTPException(status_code=400, detail=f"Cooldown in effect. Please wait {status['seconds_remaining']} seconds.")

    runtime_config = load_runtime_config(container)
    settings = runtime_config.get("settings", {})
    
    api_key = settings.get("gemini_api_key", "").strip()
    model_name = settings.get("gemini_model_name", "gemini-1.5-flash").strip()
    
    if not api_key:
        return {
            "configured": False,
            "suggestions": [],
            "overall_summary": "Gemini API key is not configured. Please enter your API Key in System > Integrations."
        }

    # Fetch data
    data = get_ai_optimization_data(container)
    
    # Construct prompt
    prompt = f"""
You are the MobGuard AI Optimizer. MobGuard is a security system that protects VPN access. It scores connection events to decide if they are coming from a MOBILE network (trusted) or a HOME/datacenter network (punished/blocked).

MobGuard Scoring logic:
- Positive score points move the decision towards MOBILE.
- Negative score points move the decision towards HOME.
- Threshold parameters:
  * threshold_mobile (default 60): score >= threshold_mobile -> verdict MOBILE.
  * threshold_home (default 60): score <= -threshold_home -> verdict HOME.
  * threshold_probable_mobile (default 40): score >= threshold_probable_mobile -> verdict MOBILE / PROBABLE.
  * threshold_probable_home (default 40): score <= -threshold_probable_home -> verdict HOME / PROBABLE.
  * If score is between thresholds, the verdict is UNSURE, which creates a manual review case for operators.

Your Goal:
Recommend threshold and weight adjustments to decrease false positives (trusted mobile users getting flagged as HOME or UNSURE) and reduce manual review cases (fewer UNSURE verdicts) while maintaining high security.

Current Rules & Settings:
{json.dumps(data["rules"], indent=2, ensure_ascii=False)}

Traffic Statistics (Last 24 hours):
- Total Events Analyzed: {data["stats_24h"]["total"]}
- Auto-resolved MOBILE: {data["stats_24h"]["mobile_count"]}
- Auto-flagged HOME: {data["stats_24h"]["home_count"]}
- Sent to manual review (UNSURE): {data["stats_24h"]["unsure_count"]}

Manual Operator Reviews (Last 7 days):
- Total Cases Resolved: {data["overrides_7d"]["total"]}
- Resolved as MOBILE (originally flagged as UNSURE/HOME by rules): {data["overrides_7d"]["resolved_mobile"]}
- Resolved as HOME (correctly flagged): {data["overrides_7d"]["resolved_home"]}

Top 10 ASNs flagged as UNSURE (Last 3 days):
{json.dumps(data["top_unsure_asns"], indent=2, ensure_ascii=False)}

Samples of UNSURE/HOME connection events (No user identities linked):
{json.dumps(data["recent_events"], indent=2, ensure_ascii=False)}

Please analyze this data. If there are many UNSURE cases resolved as MOBILE, it means thresholds might be too tight, or bonuses/penalties need adjustments. Recommend up to 4 changes to rules settings.

Respond strictly in JSON format matching the schema:
{{
  "suggestions": [
    {{
      "field_key": "threshold_mobile",
      "current_value": 60.0,
      "proposed_value": 65.0,
      "reasoning_ru": "Обоснование на русском языке...",
      "estimated_impact_percent": 14.0
    }}
  ],
  "overall_summary": "Общее заключение на русском языке..."
}}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "suggestions": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "field_key": {"type": "STRING"},
                                "current_value": {"type": "NUMBER"},
                                "proposed_value": {"type": "NUMBER"},
                                "reasoning_ru": {"type": "STRING"},
                                "estimated_impact_percent": {"type": "NUMBER"}
                            },
                            "required": ["field_key", "current_value", "proposed_value", "reasoning_ru", "estimated_impact_percent"]
                        }
                    },
                    "overall_summary": {"type": "STRING"}
                },
                "required": ["suggestions", "overall_summary"]
            }
        }
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            res_body = response.read().decode("utf-8")
            result = json.loads(res_body)
            
            # Extract text from standard Gemini response structure
            candidates = result.get("candidates", [])
            if candidates:
                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed_response = json.loads(text_content)
                parsed_response["configured"] = True
                
                # Record successful optimizer execution timestamp
                container.store.set_metadata_value("last_ai_optimizer_timestamp", datetime.utcnow().replace(microsecond=0).isoformat())
                
                return parsed_response
            else:
                raise ValueError("No candidates returned from Gemini API")
                
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8", errors="ignore")
        logger.error(f"Gemini API HTTP Error: {e.code} - {error_msg}")
        return {
            "configured": True,
            "error": f"API Error: {e.code}",
            "suggestions": [],
            "overall_summary": f"Ошибка запроса к Gemini API (HTTP {e.code}). Проверьте правильность API ключа."
        }
    except Exception as e:
        logger.exception("AI Optimizer error calling Gemini API")
        return {
            "configured": True,
            "error": str(e),
            "suggestions": [],
            "overall_summary": f"Не удалось выполнить генерацию: {str(e)}"
        }
