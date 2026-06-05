from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from api.context import build_container
from mobguard_platform.models import DecisionBundle
from mobguard_platform.module_secrets import decrypt_module_token, encrypt_module_token


ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAL_DEV_ENV_PATH = ROOT_DIR / "runtime" / "dev" / "env" / "panel.env"
DEMO_ACTOR = "local-demo-seed"
DEMO_ACTOR_TG_ID = 9001
DEMO_MODULE_ID = "local-demo-module"
DEMO_MODULE_NAME = "Local Demo Module"
DEMO_TAGS = ["LOCAL_DEMO", "LOCAL_MOBILE"]
DEMO_PREFIX = "local-demo"


def _utcnow() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _configure_local_env() -> None:
    if LOCAL_DEV_ENV_PATH.exists():
        os.environ["MOBGUARD_ENV_FILE"] = str(LOCAL_DEV_ENV_PATH)


def _container():
    _configure_local_env()
    return build_container(ROOT_DIR)


def _secret_key(container: Any) -> str:
    env_values = container.runtime.reload_env()
    secret_key = str(env_values.get("MOBGUARD_MODULE_SECRET_KEY") or "").strip()
    if not secret_key:
        raise SystemExit("MOBGUARD_MODULE_SECRET_KEY is required for demo module provisioning")
    return secret_key


def _ensure_demo_rules(container: Any) -> None:
    config_path = Path(container.runtime.config_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload.setdefault("settings", {})
    payload["settings"].setdefault("review_ui_base_url", "http://127.0.0.1:5173")
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    container.runtime.reload_config()
    container.store.sync_runtime_config(container.runtime.config)


def _existing_demo_token(container: Any, secret_key: str) -> str | None:
    module = container.store.get_module(DEMO_MODULE_ID)
    if not module:
        return None
    try:
        ciphertext = container.store.get_module_token_ciphertext(DEMO_MODULE_ID)
    except Exception:
        return None
    try:
        return decrypt_module_token(secret_key, ciphertext)
    except Exception:
        return None


def _ensure_demo_module(container: Any) -> dict[str, Any]:
    secret_key = _secret_key(container)
    token = _existing_demo_token(container, secret_key) or f"{DEMO_PREFIX}-token"
    metadata = {"inbound_tags": DEMO_TAGS}
    if not container.store.get_module(DEMO_MODULE_ID):
        token_ciphertext = encrypt_module_token(secret_key, token)
        container.store.create_managed_module(
            DEMO_MODULE_ID,
            token,
            token_ciphertext,
            module_name=DEMO_MODULE_NAME,
            metadata=metadata,
        )
    else:
        container.store.update_managed_module(
            DEMO_MODULE_ID,
            module_name=DEMO_MODULE_NAME,
            metadata=metadata,
        )
    live_rules_revision = int(container.store.get_live_rules_state()["revision"] or 1)
    container.store.register_module(
        DEMO_MODULE_ID,
        token,
        module_name=DEMO_MODULE_NAME,
        version="1.0.0-demo",
        protocol_version="v1",
        metadata=metadata,
        config_revision_applied=live_rules_revision,
        auto_create=False,
    )
    container.store.record_module_heartbeat(
        DEMO_MODULE_ID,
        status="online",
        version="1.0.0-demo",
        protocol_version="v1",
        config_revision_applied=live_rules_revision,
        details={
            "health_status": "ok",
            "error_text": "",
            "last_validation_at": _iso(_utcnow()),
            "spool_depth": 3,
            "access_log_exists": True,
            "system": {
                "cpu_percent": 12.5,
                "cpu_cores": 4,
                "load_avg_1m": 0.5,
                "load_avg_5m": 0.3,
                "load_avg_15m": 0.1,
                "memory_total_bytes": 17179869184, # 16 GB
                "memory_used_bytes": 8589934592,   # 8 GB
                "memory_percent": 50.0,
                "disk_total_bytes": 256000000000,   # 256 GB
                "disk_used_bytes": 128000000000,    # 128 GB
                "disk_percent": 50.0,
                "disk_read_bps": 1024,
                "disk_write_bps": 2048,
                "uptime_seconds": 3600,
            },
            "processes": {
                "match_count": 1,
                "cpu_percent": 1.5,
                "rss_bytes": 52428800, # 50 MB
                "vms_bytes": 104857600, # 100 MB
                "top": [
                    {
                        "pid": 1234,
                        "name": "mobguard_module",
                        "cmdline": "python -m mobguard_module",
                        "cpu_percent": 1.5,
                        "rss_bytes": 52428800,
                        "vms_bytes": 104857600,
                    }
                ],
            },
            "collected_at": _iso(_utcnow()),
        },
    )
    module = container.store.get_module(DEMO_MODULE_ID)
    if not module:
        raise SystemExit("Failed to create demo module")
    return module


def _cleanup_demo_rows(container: Any) -> None:
    with container.store._connect() as conn:
        case_rows = conn.execute(
            """
            SELECT id
            FROM review_cases
            WHERE module_id = ?
               OR uuid LIKE ?
               OR username LIKE ?
               OR ip LIKE '10.77.%'
            """,
            (DEMO_MODULE_ID, f"{DEMO_PREFIX}-%", f"{DEMO_PREFIX}-%"),
        ).fetchall()
        case_ids = [int(row["id"]) for row in case_rows]
        if case_ids:
            placeholders = ", ".join("?" for _ in case_ids)
            for table_name in ("review_labels", "review_resolutions", "review_case_ips", "review_case_modules"):
                conn.execute(f"DELETE FROM {table_name} WHERE case_id IN ({placeholders})", tuple(case_ids))
            conn.execute(f"DELETE FROM review_cases WHERE id IN ({placeholders})", tuple(case_ids))

        conn.execute(
            """
            DELETE FROM analysis_events
            WHERE module_id = ?
               OR uuid LIKE ?
               OR username LIKE ?
               OR ip LIKE '10.77.%'
            """,
            (DEMO_MODULE_ID, f"{DEMO_PREFIX}-%", f"{DEMO_PREFIX}-%"),
        )
        conn.execute("DELETE FROM ingested_raw_events WHERE module_id = ?", (DEMO_MODULE_ID,))
        conn.execute("DELETE FROM module_heartbeats WHERE module_id = ?", (DEMO_MODULE_ID,))
        conn.execute("DELETE FROM exact_ip_overrides WHERE ip LIKE '10.77.%' OR actor = ?", (DEMO_ACTOR,))
        conn.execute("DELETE FROM modules WHERE module_id = ?", (DEMO_MODULE_ID,))
        conn.commit()


def _demo_user(index: int) -> dict[str, Any]:
    return {
        "uuid": f"{DEMO_PREFIX}-uuid-{index}",
        "username": f"{DEMO_PREFIX}-user-{index}",
        "telegramId": str(9000 + index),
        "id": 9000 + index,
        "module_id": DEMO_MODULE_ID,
        "module_name": DEMO_MODULE_NAME,
    }


def _provider_evidence(provider_key: str, service_type_hint: str, *, review_recommended: bool) -> dict[str, Any]:
    return {
        "provider_key": provider_key,
        "provider_classification": "mixed",
        "service_type_hint": service_type_hint,
        "service_conflict": service_type_hint == "conflict",
        "review_recommended": review_recommended,
    }


def _open_conflict_bundle(ip: str, *, asn: int, isp: str, provider_key: str) -> DecisionBundle:
    bundle = DecisionBundle(
        ip=ip,
        verdict="UNSURE",
        confidence_band="UNSURE",
        score=0,
        asn=asn,
        isp=isp,
    )
    bundle.add_reason(
        "provider_conflict",
        "provider_profile",
        0,
        "soft",
        "NEUTRAL",
        f"Provider {provider_key} exposes both HOME and MOBILE markers",
        {
            "provider_key": provider_key,
            "provider_classification": "mixed",
            "service_type_hint": "conflict",
            "mobile_markers": ["lte", "mobile"],
            "home_markers": ["gpon", "fiber"],
        },
    )
    bundle.signal_flags["provider_evidence"] = _provider_evidence(
        provider_key,
        "conflict",
        review_recommended=True,
    )
    return bundle


def _home_bundle(ip: str, *, asn: int, isp: str, provider_key: str, score: int = -18) -> DecisionBundle:
    bundle = DecisionBundle(
        ip=ip,
        verdict="HOME",
        confidence_band="HIGH_HOME" if score <= -18 else "PROBABLE_HOME",
        score=score,
        asn=asn,
        isp=isp,
    )
    bundle.add_reason(
        "provider_home_marker",
        "provider_profile",
        -18,
        "soft",
        "HOME",
        f"Provider {provider_key} matched HOME markers",
        {
            "provider_key": provider_key,
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "home_markers": ["gpon", "fiber"],
        },
    )
    bundle.signal_flags["provider_evidence"] = _provider_evidence(
        provider_key,
        "home",
        review_recommended=True,
    )
    return bundle


def _mobile_bundle(ip: str, *, asn: int, isp: str, provider_key: str) -> DecisionBundle:
    bundle = DecisionBundle(
        ip=ip,
        verdict="MOBILE",
        confidence_band="HIGH_MOBILE",
        score=74,
        asn=asn,
        isp=isp,
    )
    bundle.add_reason(
        "provider_mobile_marker",
        "provider_profile",
        18,
        "soft",
        "MOBILE",
        f"Provider {provider_key} matched MOBILE markers",
        {
            "provider_key": provider_key,
            "provider_classification": "mixed",
            "service_type_hint": "mobile",
            "mobile_markers": ["lte", "mobile"],
        },
    )
    bundle.signal_flags["provider_evidence"] = _provider_evidence(
        provider_key,
        "mobile",
        review_recommended=False,
    )
    return bundle


def _record_case(
    container: Any,
    *,
    user: dict[str, Any],
    bundle: DecisionBundle,
    review_reason: str,
    tag: str,
    created_at: datetime,
) -> tuple[int, int]:
    event_id = container.store.record_analysis_event(
        user,
        bundle.ip,
        tag,
        bundle,
        source_event_uid=f"{DEMO_PREFIX}:{user['username']}:{bundle.ip}",
    )
    summary = container.store.ensure_review_case(user, bundle.ip, tag, bundle, event_id, review_reason)
    with container.store._connect() as conn:
        conn.execute(
            "UPDATE analysis_events SET created_at = ? WHERE id = ?",
            (_iso(created_at), event_id),
        )
        conn.execute(
            "UPDATE review_cases SET opened_at = ?, updated_at = ? WHERE id = ?",
            (_iso(created_at), _iso(created_at + timedelta(minutes=2)), summary.id),
        )
        conn.commit()
    return int(summary.id), int(event_id)


def _resolve_case(container: Any, case_id: int, event_id: int, resolution: str, created_at: datetime) -> None:
    status = "SKIPPED" if resolution == "SKIP" else "RESOLVED"
    with container.store._connect() as conn:
        conn.execute(
            """
            INSERT INTO review_resolutions (case_id, event_id, resolution, actor, actor_tg_id, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, event_id, resolution, DEMO_ACTOR, DEMO_ACTOR_TG_ID, "demo seed", _iso(created_at)),
        )
        conn.execute(
            "UPDATE review_cases SET status = ?, updated_at = ? WHERE id = ?",
            (status, _iso(created_at), case_id),
        )
        conn.commit()


def seed_demo_data() -> dict[str, Any]:
    container = _container()
    _ensure_demo_rules(container)
    _cleanup_demo_rows(container)
    module = _ensure_demo_module(container)

    base_time = _utcnow() - timedelta(minutes=18)
    open_case_ids: list[int] = []
    resolved_count = 0

    open_definitions = [
        (_demo_user(1), _open_conflict_bundle("10.77.1.10", asn=3216, isp="Local Demo ISP A", provider_key="local-demo-provider-a"), "provider_conflict", "LOCAL_DEMO", base_time),
        (_demo_user(2), _home_bundle("10.77.1.11", asn=3216, isp="Local Demo Fiber", provider_key="local-demo-provider-a", score=-12), "probable_home", "LOCAL_DEMO", base_time + timedelta(minutes=3)),
        (_demo_user(3), _open_conflict_bundle("10.77.1.12", asn=12389, isp="Local Demo Mixed ISP", provider_key="local-demo-provider-b"), "provider_conflict", "LOCAL_MOBILE", base_time + timedelta(minutes=6)),
    ]
    for user, bundle, reason, tag, created_at in open_definitions:
        case_id, _event_id = _record_case(
            container,
            user=user,
            bundle=bundle,
            review_reason=reason,
            tag=tag,
            created_at=created_at,
        )
        open_case_ids.append(case_id)

    resolved_definitions = [
        (_demo_user(4), _home_bundle("10.77.1.20", asn=3216, isp="Local Demo GPON", provider_key="local-demo-provider-a"), "provider_conflict", "LOCAL_DEMO", "HOME", base_time - timedelta(minutes=10)),
        (_demo_user(5), _mobile_bundle("10.77.1.21", asn=12389, isp="Local Demo LTE", provider_key="local-demo-provider-b"), "manual_review", "LOCAL_MOBILE", "MOBILE", base_time - timedelta(minutes=7)),
        (_demo_user(6), _open_conflict_bundle("10.77.1.22", asn=42424, isp="Local Demo Unknown", provider_key="local-demo-provider-c"), "provider_conflict", "LOCAL_MOBILE", "SKIP", base_time - timedelta(minutes=4)),
    ]
    for user, bundle, reason, tag, resolution, created_at in resolved_definitions:
        case_id, event_id = _record_case(
            container,
            user=user,
            bundle=bundle,
            review_reason=reason,
            tag=tag,
            created_at=created_at,
        )
        _resolve_case(container, case_id, event_id, resolution, created_at + timedelta(minutes=1))
        resolved_count += 1

    overview = container.store.get_overview_metrics()
    modules = container.store.list_modules(include_counters=True)
    return {
        "module_id": module["module_id"],
        "module_name": module["module_name"],
        "open_cases_seeded": len(open_case_ids),
        "resolved_cases_seeded": resolved_count,
        "overview_open_cases": overview["quality"].get("open_cases"),
        "overview_total_cases": overview["quality"].get("total_cases"),
        "modules_count": len(modules),
    }


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Seed local MobGuard demo data into the current runtime database."
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    result = seed_demo_data()
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
