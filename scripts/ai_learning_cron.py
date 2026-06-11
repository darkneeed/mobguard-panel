from __future__ import annotations

import argparse
import json
import os
import urllib.request
import urllib.error
import ipaddress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mobguard_platform import load_runtime_context

def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()

def send_telegram_alert(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            pass
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

def run_ai_audit(runtime=None, store=None) -> None:
    if runtime is None or store is None:
        from mobguard_platform.storage.factory import build_storage_bundle

        root_dir = Path(__file__).resolve().parents[1]
        runtime = load_runtime_context(root_dir, os.getenv("BAN_SYSTEM_DIR"))
        storage_bundle = build_storage_bundle(runtime)
        store = storage_bundle.store
    
    # 1. Load Gemini configurations
    settings = runtime.config.get("settings", {})
    api_key = settings.get("gemini_api_key", "").strip()
    model_name = settings.get("gemini_model_name", "gemini-flash-latest").strip()
    
    if not api_key:
        print("Gemini API key is not configured. Skipping AI auto-learning audit.")
        return
        
    print(f"Starting AI Auto-Learning Audit using model {model_name}...")
    
    # 2. Collect Grey-Zone and Cold-Start patterns
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).replace(microsecond=0).isoformat()
    
    patterns_to_audit = [] # list of dict: {type, value, current_decision}
    
    with store._connect() as conn:
        # A. Grey zones from learning_pattern_stats
        rows_grey = conn.execute(
            """
            SELECT pattern_type, pattern_value, decision, precision, total
            FROM learning_pattern_stats
            WHERE precision >= 0.60 AND precision <= 0.88 AND total >= 5
            """
        ).fetchall()
        for r in rows_grey:
            row_dict = dict(r)
            patterns_to_audit.append({
                "type": row_dict["pattern_type"],
                "value": row_dict["pattern_value"],
                "current_decision": row_dict["decision"],
                "reason": f"Grey Zone (precision {row_dict['precision']:.2f}, total {row_dict['total']})"
            })
            
        # B. Cold Start ASNs (OPEN review cases >= 15)
        rows_asn = conn.execute(
            """
            SELECT asn, isp, COUNT(*) as count
            FROM review_cases
            WHERE status = 'OPEN' AND asn IS NOT NULL AND asn != 0
            GROUP BY asn, isp
            HAVING COUNT(*) >= 15
            """
        ).fetchall()
        for r in rows_asn:
            row_dict = dict(r)
            patterns_to_audit.append({
                "type": "asn",
                "value": str(row_dict["asn"]),
                "current_decision": "UNSURE",
                "reason": f"Cold Start ASN (OPEN cases: {row_dict['count']}, ISP: {row_dict['isp']})"
            })
            
        # C. Cold Start Provider Keys (OPEN review cases >= 15)
        rows_prov = conn.execute(
            """
            SELECT provider_key, COUNT(*) as count
            FROM review_cases
            WHERE status = 'OPEN' AND provider_key IS NOT NULL AND provider_key != ''
            GROUP BY provider_key
            HAVING COUNT(*) >= 15
            """
        ).fetchall()
        for r in rows_prov:
            row_dict = dict(r)
            patterns_to_audit.append({
                "type": "provider",
                "value": row_dict["provider_key"],
                "current_decision": "UNSURE",
                "reason": f"Cold Start Provider (OPEN cases: {row_dict['count']})"
            })

    # Deduplicate patterns
    seen_patterns = set()
    unique_patterns = []
    for pat in patterns_to_audit:
        key = (pat["type"], pat["value"])
        if key not in seen_patterns:
            seen_patterns.add(key)
            unique_patterns.append(pat)
            
    if not unique_patterns:
        print("No patterns require AI auto-learning audit today.")
        return
        
    print(f"Found {len(unique_patterns)} patterns for AI audit. Collecting case details...")
    
    # 3. Gather details/context for each pattern
    patterns_data = []
    
    with store._connect() as conn:
        for pat in unique_patterns:
            p_type = pat["type"]
            p_val = pat["value"]
            
            # Fetch cases related to pattern
            cases = []
            if p_type == "asn":
                rows_cases = conn.execute(
                    """
                    SELECT id, ip, verdict, status, client_os_family, client_app_name, isp
                    FROM review_cases
                    WHERE asn = ?
                    ORDER BY updated_at DESC
                    LIMIT 30
                    """,
                    (int(p_val) if p_val.isdigit() else 0,)
                ).fetchall()
            elif p_type == "provider":
                rows_cases = conn.execute(
                    """
                    SELECT id, ip, verdict, status, client_os_family, client_app_name, isp
                    FROM review_cases
                    WHERE provider_key = ?
                    ORDER BY updated_at DESC
                    LIMIT 30
                    """,
                    (p_val,)
                ).fetchall()
            elif p_type == "subnet":
                # For subnets, we fetch recent cases and filter in Python
                rows_cases = conn.execute(
                    """
                    SELECT id, ip, verdict, status, client_os_family, client_app_name, isp
                    FROM review_cases
                    ORDER BY updated_at DESC
                    LIMIT 300
                    """
                ).fetchall()
            else:
                rows_cases = []
                
            # Parse rows into list of dicts
            for r in rows_cases:
                r_dict = dict(r)
                if p_type == "subnet":
                    # Check if IP matches subnet
                    try:
                        ip_obj = ipaddress.ip_address(r_dict["ip"])
                        net_obj = ipaddress.ip_network(p_val)
                        if ip_obj not in net_obj:
                            continue
                    except Exception:
                        continue
                        
                cases.append({
                    "case_id": r_dict["id"],
                    "ip": r_dict["ip"],
                    "operator_verdict": r_dict["verdict"],
                    "status": r_dict["status"],
                    "os": r_dict["client_os_family"],
                    "app": r_dict["client_app_name"],
                    "isp": r_dict["isp"]
                })
                if len(cases) >= 30:
                    break
            
            # Aggregate stats
            os_stats = {}
            verdict_stats = {}
            isp_names = set()
            for c in cases:
                client_os = c["os"] or "Unknown"
                os_stats[client_os] = os_stats.get(client_os, 0) + 1
                
                verd = c["operator_verdict"] or "UNSURE"
                verdict_stats[verd] = verdict_stats.get(verd, 0) + 1
                
                if c["isp"]:
                    isp_names.add(c["isp"])
                    
            patterns_data.append({
                "pattern_type": p_type,
                "pattern_value": p_val,
                "current_decision": pat["current_decision"],
                "audit_reason": pat["reason"],
                "isp_names": list(isp_names)[:5],
                "verdict_distribution": verdict_stats,
                "os_distribution": os_stats,
                "cases_samples": cases[:10] # up to 10 sample cases (strictly no user profile fields)
            })

    # 4. Prompt Gemini with structured output
    prompt = f"""
You are the MobGuard AI Learning Auditor. Your job is to analyze "grey zones" (subnets/ASNs with high variance in operator decisions) and "cold starts" (frequently flagged new networks).
You must also audit operator decisions to detect cases where the operator approved a connection (resolved as MOBILE) which is actually a hosting provider, VPS, VPN, or datacenter, or blocked a connection (resolved as HOME) that is actually a residential ISP/mobile provider.

For each of the following network patterns, analyze the ISP names, OS distributions, and sample cases.
Classify the network and detect any wrong operator decisions (operator errors).

Patterns to Analyze:
{json.dumps(patterns_data, indent=2, ensure_ascii=False)}

For each analyzed pattern, produce:
1. `pattern_type`: same as input
2. `pattern_value`: same as input
3. `suggested_decision`: classification verdict:
   - 'MOBILE': Legitimate mobile operator.
   - 'HOME': Residential ISP / home broadband.
   - 'HOSTING': VPS, cloud hosting, proxy, VPN.
   - 'MIXED': Combined residential and mobile/hosting traffic.
4. `confidence`: float (0.0 to 1.0)
5. `reasoning_ru`: A detailed explanation on why this classification was chosen (in Russian). Include ISP details, OS observations, and network background.
6. `operator_errors`: list of integers (case IDs of erroneous operator resolutions, e.g., if a case was resolved as MOBILE but the ISP is clearly hosting like Hetzner, DigitalOcean, OVH, or Vultr).
7. `suggested_provider_profile`: (optional object) If pattern_type is 'provider' or if you recommend configuring a new operator/provider profile in the configuration to map this network / ASN, include this object matching the schema:
   - `key`: lowercase ASCII string representing the provider identifier (e.g. 'vultr', 'mts').
   - `classification`: one of: 'mixed', 'mobile', 'home'.
   - `aliases`: list of lowercase string aliases/keywords matching this provider (e.g. ['vultr']).
   - `mobile_markers`: list of lowercase string markers (e.g. ['mobile', 'lte', 'pgw']).
   - `home_markers`: list of lowercase string markers (e.g. ['fiber', 'gpon', 'fttb']).
   - `asns`: list of integers (ASNs belonging to this operator).

Respond strictly in JSON format matching the schema:
{{
  "suggestions": [
    {{
      "pattern_type": "asn",
      "pattern_value": "12345",
      "suggested_decision": "HOSTING",
      "confidence": 0.98,
      "reasoning_ru": "Этот ASN принадлежит хостинг-провайдеру...",
      "operator_errors": [1024, 1025],
      "suggested_provider_profile": {{
        "key": "hostingco",
        "classification": "home",
        "aliases": ["hostingco"],
        "mobile_markers": [],
        "home_markers": ["fiber"],
        "asns": [12345]
      }}
    }}
  ]
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
                                "pattern_type": {"type": "STRING"},
                                "pattern_value": {"type": "STRING"},
                                "suggested_decision": {"type": "STRING"},
                                "confidence": {"type": "NUMBER"},
                                "reasoning_ru": {"type": "STRING"},
                                "operator_errors": {
                                    "type": "ARRAY",
                                    "items": {"type": "INTEGER"}
                                },
                                "suggested_provider_profile": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "key": {"type": "STRING"},
                                        "classification": {"type": "STRING"},
                                        "aliases": {
                                            "type": "ARRAY",
                                            "items": {"type": "STRING"}
                                        },
                                        "mobile_markers": {
                                            "type": "ARRAY",
                                            "items": {"type": "STRING"}
                                        },
                                        "home_markers": {
                                            "type": "ARRAY",
                                            "items": {"type": "STRING"}
                                        },
                                        "asns": {
                                            "type": "ARRAY",
                                            "items": {"type": "INTEGER"}
                                        }
                                    },
                                    "required": ["key", "classification", "aliases", "mobile_markers", "home_markers", "asns"]
                                }
                            },
                            "required": ["pattern_type", "pattern_value", "suggested_decision", "confidence", "reasoning_ru", "operator_errors"]
                        }
                    }
                },
                "required": ["suggestions"]
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
        with urllib.request.urlopen(req, timeout=90) as response:
            res_body = response.read().decode("utf-8")
            result = json.loads(res_body)
            candidates = result.get("candidates", [])
            if not candidates:
                print("No candidates returned from Gemini API.")
                return
                
            text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            suggestions_data = json.loads(text_content).get("suggestions", [])
            
            # Record last successful suggestions audit timestamp
            store.set_metadata_value("last_ai_suggestions_timestamp", datetime.utcnow().replace(microsecond=0).isoformat())
            
            print(f"Gemini returned {len(suggestions_data)} recommendations.")
            
            # 5. Save recommendations to database
            now = _utcnow()
            saved_count = 0
            operator_errors_count = 0
            
            with store._connect() as conn:
                for sug in suggestions_data:
                    curr_dec = next((p["current_decision"] for p in unique_patterns if p["type"] == sug["pattern_type"] and p["value"] == sug["pattern_value"]), None)
                    has_changes = (
                        (sug["suggested_decision"] != curr_dec) or
                        (sug.get("operator_errors") and len(sug["operator_errors"]) > 0) or
                        (sug.get("suggested_provider_profile") is not None)
                    )
                    if not has_changes:
                        continue

                    # Check if already exists in status PENDING
                    existing = conn.execute(
                        """
                        SELECT id FROM ai_learning_suggestions 
                        WHERE pattern_type = ? AND pattern_value = ? AND status = 'PENDING'
                        """,
                        (sug["pattern_type"], sug["pattern_value"])
                    ).fetchone()
                    
                    prof_val = sug.get("suggested_provider_profile")
                    prof_json = json.dumps(prof_val, ensure_ascii=False) if prof_val else None
                    if existing:
                        # Update existing
                        conn.execute(
                            """
                            UPDATE ai_learning_suggestions
                            SET suggested_decision = ?,
                                confidence = ?,
                                reasoning_ru = ?,
                                operator_errors_json = ?,
                                suggested_provider_profile_json = ?,
                                updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                sug["suggested_decision"],
                                sug["confidence"],
                                sug["reasoning_ru"],
                                json.dumps(sug["operator_errors"]),
                                prof_json,
                                now,
                                existing["id"] if "id" in existing.keys() else existing[0]
                            )
                        )
                    else:
                        # Insert new
                        conn.execute(
                            """
                            INSERT INTO ai_learning_suggestions (
                                pattern_type, pattern_value, current_decision, suggested_decision,
                                confidence, reasoning_ru, operator_errors_json, suggested_provider_profile_json, status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                            """,
                            (
                                sug["pattern_type"],
                                sug["pattern_value"],
                                next((p["current_decision"] for p in unique_patterns if p["type"] == sug["pattern_type"] and p["value"] == sug["pattern_value"]), None),
                                sug["suggested_decision"],
                                sug["confidence"],
                                sug["reasoning_ru"],
                                json.dumps(sug["operator_errors"]),
                                prof_json,
                                now,
                                now
                            )
                        )
                    saved_count += 1
                    operator_errors_count += len(sug["operator_errors"])
                conn.commit()
                
            print(f"Saved/Updated {saved_count} AI suggestions in DB.")
            
            # 6. Optional Telegram Alert to Admin
            try:
                from api.services.runtime_state import load_env_values
                env_values = load_env_values(store)
                tg_token = str(env_values.get("TG_ADMIN_BOT_TOKEN") or "").strip()
            except Exception:
                tg_token = os.getenv("TG_ADMIN_BOT_TOKEN", "").strip()
            tg_chat_id = str(settings.get("tg_admin_chat_id") or "").strip()
            
            if tg_token and tg_chat_id and saved_count > 0:
                msg = (
                    f"🤖 <b>ИИ-Аудит автообучения MobGuard</b>\n"
                    f"Выявлено новых рекомендаций: <b>{saved_count}</b>\n"
                    f"Подозрения на ошибки операторов: <b>{operator_errors_count}</b> кейсов.\n\n"
                    f"Пожалуйста, проверьте вкладку <i>База знаний > Рекомендации ИИ</i> для модерации."
                )
                send_telegram_alert(tg_token, tg_chat_id, msg)
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"Error executing AI audit: {e}")

def main() -> int:
    run_ai_audit()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
