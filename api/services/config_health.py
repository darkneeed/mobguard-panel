from __future__ import annotations

from typing import Any
from ..context import APIContainer
from .automation_status import build_automation_status
from .runtime_state import load_env_values

def get_config_health(container: APIContainer) -> dict[str, Any]:
    # 1. Режим работы
    auto_status = build_automation_status(container)
    mode = auto_status.get("mode", "observe")
    
    if mode == "enforce":
        automation_status_check = {
            "key": "automation_mode",
            "status": "ok",
            "label": "Режим работы",
            "detail": "Активен (Enforce)",
            "link": "/rules/general"
        }
    elif mode == "warning_only":
        automation_status_check = {
            "key": "automation_mode",
            "status": "warn",
            "label": "Режим работы",
            "detail": "Только предупреждения (Warning only)",
            "link": "/rules/general"
        }
    else: # observe
        automation_status_check = {
            "key": "automation_mode",
            "status": "error",
            "label": "Режим работы",
            "detail": "Только наблюдение (Observe / Dry-run)",
            "link": "/rules/general"
        }

    # 2. Pure Mobile ASN
    live_state = container.store.get_live_rules_state()
    rules = live_state.get("rules", {})
    pure_mobile_asns = rules.get("pure_mobile_asns", [])
    asn_count = len(pure_mobile_asns) if isinstance(pure_mobile_asns, list) else 0
    
    if asn_count >= 3:
        asn_status = "ok"
    elif asn_count >= 1:
        asn_status = "warn"
    else:
        asn_status = "error"
        
    asn_check = {
        "key": "pure_mobile_asn",
        "status": asn_status,
        "label": "Pure Mobile ASN",
        "detail": f"Настроено ASN: {asn_count}",
        "link": "/rules/lists"
    }

    # 3. IPInfo токен
    env_values = load_env_values(container)
    ipinfo_token = env_values.get("IPINFO_TOKEN")
    
    if ipinfo_token and ipinfo_token.strip():
        ipinfo_status = "ok"
        ipinfo_detail = "Токен присутствует"
    else:
        ipinfo_status = "error"
        ipinfo_detail = "Токен отсутствует"
        
    ipinfo_check = {
        "key": "ipinfo_token",
        "status": ipinfo_status,
        "label": "IPInfo токен",
        "detail": ipinfo_detail,
        "link": "/rules/general"
    }

    # 4. Telegram бот
    tg_token = env_values.get("TG_ADMIN_BOT_TOKEN")
    tg_username = env_values.get("TG_ADMIN_BOT_USERNAME")
    
    if tg_token and tg_token.strip() and tg_username and tg_username.strip():
        tg_status = "ok"
        tg_detail = f"Бот настроен (@{tg_username.strip('@')})"
    elif tg_token and tg_token.strip():
        tg_status = "warn"
        tg_detail = "Настроен только токен (без username)"
    else:
        tg_status = "error"
        tg_detail = "Не настроен"
        
    tg_check = {
        "key": "telegram_bot",
        "status": tg_status,
        "label": "Telegram бот",
        "detail": tg_detail,
        "link": "/telegram"
    }

    # 5. Promoted patterns
    with container.store._connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM learning_patterns_active").fetchone()
        promoted_count = row["cnt"] if row else 0
        
    if promoted_count >= 5:
        promoted_status = "ok"
    elif promoted_count >= 1:
        promoted_status = "warn"
    else:
        promoted_status = "error"
        
    promoted_check = {
        "key": "promoted_patterns",
        "status": promoted_status,
        "label": "Promoted patterns",
        "detail": f"Активных паттернов: {promoted_count}",
        "link": "/data/learning"
    }

    # 6. Score zero ratio
    health_snapshot = container.store.get_health_snapshot()
    analysis_24h = health_snapshot.get("analysis_24h", {})
    score_zero_ratio = analysis_24h.get("score_zero_ratio", 0.0)
    
    ratio_pct = score_zero_ratio * 100
    if score_zero_ratio < 0.10:
        ratio_status = "ok"
    elif score_zero_ratio <= 0.30:
        ratio_status = "warn"
    else:
        ratio_status = "error"
        
    ratio_check = {
        "key": "score_zero_ratio",
        "status": ratio_status,
        "label": "Score zero ratio",
        "detail": f"Доля нулевых скоров: {ratio_pct:.1f}%",
        "link": "/data/events"
    }

    return {
        "checks": [
            automation_status_check,
            asn_check,
            ipinfo_check,
            tg_check,
            promoted_check,
            ratio_check
        ]
    }
