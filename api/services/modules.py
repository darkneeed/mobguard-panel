from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import textwrap
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from behavioral_analyzers import BehavioralEngine
from mobguard_core.scoring import ScoringContext, ScoringDependencies, evaluate_mobile_network
from mobguard_platform import (
    DecisionBundle,
    apply_remote_access_state,
    apply_remote_traffic_cap,
    build_auto_restriction_state,
    review_reason_for_bundle,
    should_warning_only,
)
from mobguard_platform.module_secrets import ModuleSecretError, decrypt_module_token, encrypt_module_token
from mobguard_platform.panel_client import PanelClient
from mobguard_platform.runtime import read_env_file
from mobguard_platform.runtime_admin_defaults import ENFORCEMENT_SETTINGS_DEFAULTS

from ..context import APIContainer


PROTOCOL_VERSION = "v1"
MODULE_TOKEN_PLACEHOLDER = "__PASTE_TOKEN__"
DEFAULT_ACCESS_LOG_PATH = "/var/log/remnanode/access.log"
DEFAULT_STATE_DIR = "./state"
DEFAULT_SPOOL_DIR = "./state/spool"


def _ipinfo_client():
    try:
        from ipinfo_api import ipinfo_api
    except ImportError as exc:
        raise RuntimeError(
            "Module ingestion dependencies are missing in mobguard-api image: install aiohttp and rebuild the API image"
        ) from exc
    return ipinfo_api


def _require_protocol_version(protocol_version: str) -> str:
    normalized = str(protocol_version or "").strip() or PROTOCOL_VERSION
    if normalized != PROTOCOL_VERSION:
        raise ValueError(f"Unsupported module protocol version: {normalized}")
    return normalized


def _runtime_settings(container: APIContainer) -> dict[str, Any]:
    return container.store.get_live_rules_state()["rules"].get("settings", {})


def _module_runtime(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "heartbeat_interval_seconds": int(settings.get("module_heartbeat_interval_seconds", 30)),
        "config_poll_interval_seconds": int(settings.get("module_config_poll_interval_seconds", 60)),
        "flush_interval_seconds": int(settings.get("module_flush_interval_seconds", 3)),
        "event_batch_size": int(settings.get("module_event_batch_size", 100)),
        "max_spool_events": int(settings.get("module_max_spool_events", 5000)),
    }


def _remnawave_client(container: APIContainer) -> PanelClient:
    settings = _runtime_settings(container)
    base_url = str(settings.get("remnawave_api_url") or settings.get("panel_url") or "").strip()
    token = (
        os.getenv("REMNAWAVE_API_TOKEN")
        or os.getenv("PANEL_TOKEN")
        or ""
    )
    return PanelClient(base_url, token)


def _module_secret_key(container: APIContainer) -> str:
    env_values = read_env_file(str(container.runtime.env_path))
    secret_key = str(
        os.getenv("MOBGUARD_MODULE_SECRET_KEY")
        or env_values.get("MOBGUARD_MODULE_SECRET_KEY")
        or ""
    ).strip()
    if not secret_key:
        raise ValueError("MOBGUARD_MODULE_SECRET_KEY is not configured")
    return secret_key


def _normalize_api_base_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if not normalized:
        return ""
    return normalized if normalized.endswith("/api") else f"{normalized}/api"


def _panel_base_url(container: APIContainer) -> str:
    runtime_settings = {}
    runtime_config = getattr(container.runtime, "config", None)
    if isinstance(runtime_config, dict):
        runtime_settings = runtime_config.get("settings", {}) if isinstance(runtime_config.get("settings", {}), dict) else {}
    settings = _runtime_settings(container)
    public_ui_base = str(
        runtime_settings.get("review_ui_base_url")
        or settings.get("review_ui_base_url")
        or ""
    ).strip()
    if public_ui_base:
        return _normalize_api_base_url(public_ui_base)
    fallback_base = str(
        runtime_settings.get("panel_url")
        or settings.get("panel_url")
        or runtime_settings.get("remnawave_api_url")
        or settings.get("remnawave_api_url")
        or ""
    ).strip()
    return _normalize_api_base_url(fallback_base) or "__SET_PANEL_BASE_URL__/api"


def _yaml_string(value: Any) -> str:
    return '"' + str(value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalize_config_profiles(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("config_profiles must be a list")
    profiles = [str(item or "").strip() for item in values]
    cleaned = [item for item in profiles if item]
    if not cleaned:
        raise ValueError("config_profiles must contain at least one profile name")
    return cleaned


def _module_metadata_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    module_name = str(payload.get("module_name") or "").strip()
    host = str(payload.get("host") or "").strip()
    access_log_path = str(payload.get("access_log_path") or DEFAULT_ACCESS_LOG_PATH).strip()
    provider = str(payload.get("provider") or "").strip()
    notes = str(payload.get("notes") or "").strip()
    if not module_name:
        raise ValueError("module_name is required")
    if not host:
        raise ValueError("host is required")
    try:
        port = int(payload.get("port") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("port must be an integer") from exc
    if port <= 0 or port > 65535:
        raise ValueError("port must be between 1 and 65535")
    if not access_log_path:
        raise ValueError("access_log_path is required")
    return {
        "module_name": module_name,
        "metadata": {
            "host": host,
            "port": port,
            "access_log_path": access_log_path,
            "config_profiles": _normalize_config_profiles(payload.get("config_profiles") or []),
            "provider": provider,
            "notes": notes,
        },
    }


def _module_install_payload(container: APIContainer, module: dict[str, Any]) -> dict[str, Any]:
    config_profiles = module.get("config_profiles") or []
    access_log_path = module.get("access_log_path") or DEFAULT_ACCESS_LOG_PATH
    log_mount = f"{access_log_path}:{access_log_path}:ro"
    compose_yaml = textwrap.dedent(
        f"""\
        # MobGuard module install bundle
        # Module: {module.get("module_name") or module.get("module_id")}
        # Host metadata: {module.get("host") or "n/a"}
        # Port metadata: {module.get("port") or "n/a"}
        # Config profiles: {", ".join(config_profiles) if config_profiles else "n/a"}
        # Copy the token from the panel and replace {MODULE_TOKEN_PLACEHOLDER} before start.
        services:
          mobguard-module:
            build:
              context: .
              dockerfile: Dockerfile
            container_name: {module.get("module_id") or "mobguard-module"}
            restart: unless-stopped
            environment:
              PANEL_BASE_URL: {_yaml_string(_panel_base_url(container))}
              MODULE_ID: {_yaml_string(module.get("module_id") or "")}
              MODULE_TOKEN: {_yaml_string(MODULE_TOKEN_PLACEHOLDER)}
              ACCESS_LOG_PATH: {_yaml_string(access_log_path)}
              STATE_DIR: {_yaml_string(DEFAULT_STATE_DIR)}
              SPOOL_DIR: {_yaml_string(DEFAULT_SPOOL_DIR)}
            volumes:
              - ./state:/app/state
              - {_yaml_string(log_mount)}
        """
    ).strip()
    return {"compose_yaml": compose_yaml}


def _module_detail_response(container: APIContainer, module: dict[str, Any]) -> dict[str, Any]:
    return {"module": module, "install": _module_install_payload(container, module)}


def _generate_module_id(container: APIContainer) -> str:
    for _ in range(10):
        candidate = f"module-{uuid.uuid4().hex[:12]}"
        if not container.store.get_module(candidate):
            return candidate
    raise ValueError("Failed to generate a unique module_id")


def _event_uid(module_id: str, payload: dict[str, Any]) -> str:
    raw_uid = str(payload.get("event_uid") or "").strip()
    if raw_uid:
        return raw_uid
    fallback = "|".join(
        [
            str(module_id),
            str(payload.get("log_offset") or ""),
            str(payload.get("occurred_at") or ""),
            str(payload.get("uuid") or ""),
            str(payload.get("system_id") or ""),
            str(payload.get("telegram_id") or ""),
            str(payload.get("ip") or ""),
            str(payload.get("tag") or ""),
        ]
    )
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


async def _resolve_remote_user(
    container: APIContainer,
    client: PanelClient,
    payload: dict[str, Any],
) -> dict[str, Any]:
    identifier = next(
        (
            value
            for value in (
                payload.get("uuid"),
                payload.get("system_id"),
                payload.get("telegram_id"),
                payload.get("username"),
            )
            if value not in (None, "")
        ),
        None,
    )
    remote_user = {}
    if identifier not in (None, "") and client.enabled:
        remote_user = await asyncio.to_thread(client.get_user_data, str(identifier).strip()) or {}
    user_data = dict(remote_user)
    if payload.get("uuid") and not user_data.get("uuid"):
        user_data["uuid"] = payload["uuid"]
    if payload.get("username") and not user_data.get("username"):
        user_data["username"] = payload["username"]
    if payload.get("system_id") not in (None, "") and user_data.get("id") is None:
        user_data["id"] = int(payload["system_id"])
    if payload.get("telegram_id") not in (None, "") and user_data.get("telegramId") is None:
        user_data["telegramId"] = str(payload["telegram_id"])
    return user_data


async def _analyze_event(
    container: APIContainer,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    rules: dict[str, Any],
) -> DecisionBundle:
    ipinfo = _ipinfo_client()

    async def get_manual_override(target_ip: str) -> Optional[str]:
        manual_decision = await container.store.async_get_ip_override(target_ip)
        if manual_decision:
            return manual_decision
        return await container.analysis_store.get_unsure_pattern(target_ip)

    behavior_engine = BehavioralEngine(container.analysis_store, rules)

    async def analyze_behavior(current_uuid: str, target_ip: str, current_tag: str) -> dict[str, Any]:
        result = await behavior_engine.analyze(current_uuid, target_ip, current_tag)
        result["subnet"] = container.analysis_store.get_subnet(target_ip)
        return result

    def record_stats(asn: Optional[int], status: str, matched_kw: Optional[str], org: str) -> None:
        # Daily/stat buffers are not part of the panel control-plane contract in v1.
        return None

    bundle = await evaluate_mobile_network(
        context=ScoringContext(
            ip=str(payload["ip"]),
            uuid=str(user_data.get("uuid") or "") or None,
            tag=str(payload.get("tag") or "") or None,
        ),
        config=rules,
        deps=ScoringDependencies(
            get_manual_override=get_manual_override,
            get_ip_info=ipinfo.get_ip_info,
            parse_asn=ipinfo.parse_asn,
            normalize_isp_name=ipinfo.normalize_isp_name,
            is_datacenter=ipinfo.is_datacenter,
            analyze_behavior=analyze_behavior,
            get_promoted_pattern=container.store.async_get_promoted_pattern,
            get_legacy_confidence=container.analysis_store.get_learning_confidence,
            check_ip_api_mobile=lambda _: asyncio.sleep(0, result=None),
            record_decision=behavior_engine.record_decision,
            record_stats=record_stats,
        ),
    )
    return bundle


async def _apply_enforcement_if_needed(
    container: APIContainer,
    client: PanelClient,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    bundle: DecisionBundle,
    rules: dict[str, Any],
) -> Optional[dict[str, Any]]:
    settings = rules.get("settings", {})
    if bundle.verdict != "HOME" or bundle.confidence_band not in {"HIGH_HOME", "PROBABLE_HOME"}:
        return None
    uuid = str(user_data.get("uuid") or "").strip()
    if not uuid:
        return None

    warning_only = (
        bool(settings.get("warning_only_mode", False))
        or bool(settings.get("shadow_mode", True))
        or should_warning_only(bundle)
        or not bundle.punitive_eligible
    )
    now = datetime.utcnow().replace(microsecond=0)
    row = await container.analysis_store.fetch_one(
        """
        SELECT strikes, warning_count
        FROM violations
        WHERE uuid = ?
        """,
        (uuid,),
    )
    strikes = int(row["strikes"]) if row and row["strikes"] is not None else 0
    warning_count = int(row["warning_count"]) if row and row["warning_count"] is not None else 0

    if warning_only:
        next_warning_count = warning_count + 1
        await container.analysis_store.execute(
            """
            INSERT INTO violations (
                uuid, strikes, unban_time, last_forgiven, last_strike_time,
                warning_time, warning_count, restriction_mode,
                saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, 'SQUAD', NULL, NULL, NULL)
            ON CONFLICT(uuid) DO UPDATE SET
                warning_time = excluded.warning_time,
                warning_count = excluded.warning_count,
                last_strike_time = excluded.last_strike_time
            """,
            (
                uuid,
                strikes,
                now.isoformat(),
                now.isoformat(),
                now.isoformat(),
                next_warning_count,
            ),
        )
        return {
            "type": "warning",
            "warning_count": next_warning_count,
            "warning_only": True,
        }

    durations = settings.get(
        "ban_durations_minutes",
        ENFORCEMENT_SETTINGS_DEFAULTS["ban_durations_minutes"],
    )
    if not isinstance(durations, list) or not durations:
        durations = ENFORCEMENT_SETTINGS_DEFAULTS["ban_durations_minutes"]
    next_strike = max(strikes, 0) + 1
    duration = int(durations[min(next_strike - 1, len(durations) - 1)])
    restriction_state = build_auto_restriction_state(user_data, settings)
    unban_time = now + timedelta(minutes=duration)
    await container.analysis_store.execute(
        """
        INSERT INTO violations (
            uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count,
            restriction_mode, saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
        ) VALUES (?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, ?)
        ON CONFLICT(uuid) DO UPDATE SET
            strikes = excluded.strikes,
            unban_time = excluded.unban_time,
            last_forgiven = excluded.last_forgiven,
            last_strike_time = excluded.last_strike_time,
            warning_time = NULL,
            warning_count = 0,
            restriction_mode = excluded.restriction_mode,
            saved_traffic_limit_bytes = excluded.saved_traffic_limit_bytes,
            saved_traffic_limit_strategy = excluded.saved_traffic_limit_strategy,
            applied_traffic_limit_bytes = excluded.applied_traffic_limit_bytes
        """,
        (
            uuid,
            next_strike,
            unban_time.isoformat(),
            now.isoformat(),
            now.isoformat(),
            restriction_state["restriction_mode"],
            restriction_state["saved_traffic_limit_bytes"],
            restriction_state["saved_traffic_limit_strategy"],
            restriction_state["applied_traffic_limit_bytes"],
        ),
    )
    await container.analysis_store.execute(
        """
        INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid,
            str(payload.get("ip") or ""),
            str(bundle.isp or ""),
            bundle.asn,
            str(payload.get("tag") or ""),
            next_strike,
            duration,
            now.isoformat(),
        ),
    )
    if bool(settings.get("dry_run", True)) or not client.enabled:
        return {
            "type": "ban",
            "strike": next_strike,
            "ban_minutes": duration,
            "remote_updated": False,
            "dry_run": True,
        }

    def _remote_apply() -> bool:
        if restriction_state["restriction_mode"] == "TRAFFIC_CAP":
            result = apply_remote_traffic_cap(
                client,
                uuid,
                user_data,
                int(settings.get("traffic_cap_increment_gb", ENFORCEMENT_SETTINGS_DEFAULTS["traffic_cap_increment_gb"])),
            )
            return bool(result["remote_updated"])
        return apply_remote_access_state(client, uuid, settings, restricted=True)

    remote_updated = await asyncio.to_thread(_remote_apply)
    return {
        "type": "ban",
        "strike": next_strike,
        "ban_minutes": duration,
        "remote_updated": bool(remote_updated),
        "dry_run": False,
    }


async def _process_module_event(
    container: APIContainer,
    module: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    rules_state = container.store.get_live_rules_state()
    rules = rules_state["rules"]
    raw_ip = str(payload.get("ip") or "").strip()
    if not raw_ip:
        raise ValueError("Raw event is missing ip")

    user_data = await _resolve_remote_user(container, _remnawave_client(container), payload)
    user_data["module_id"] = module["module_id"]
    user_data["module_name"] = module["module_name"]

    exempt_ids = {int(value) for value in rules.get("exempt_ids", [])}
    exempt_tg_ids = {int(value) for value in rules.get("exempt_tg_ids", [])}
    system_id = user_data.get("id")
    telegram_id = user_data.get("telegramId")
    if system_id is not None and int(system_id) in exempt_ids:
        return {"status": "skipped", "reason": "exempt_system_id"}
    if telegram_id not in (None, "") and int(telegram_id) in exempt_tg_ids:
        return {"status": "skipped", "reason": "exempt_telegram_id"}

    manual_override = await container.store.async_get_ip_override(raw_ip)
    cached = None
    if not manual_override:
        manual_override = await container.analysis_store.get_unsure_pattern(raw_ip)
    if not manual_override:
        cached = await container.analysis_store.get_cached_decision(raw_ip)

    if cached:
        bundle = DecisionBundle.from_cache_record(raw_ip, cached)
    else:
        bundle = await _analyze_event(container, user_data, payload, rules)
        await container.analysis_store.cache_decision(raw_ip, bundle.to_cache_payload())

    event_id = await container.store.async_record_analysis_event(
        user_data,
        raw_ip,
        str(payload.get("tag") or ""),
        bundle,
    )
    bundle.event_id = event_id

    review_case_id: Optional[int] = None
    review_reason = review_reason_for_bundle(bundle)
    if review_reason:
        review_case = await container.store.async_ensure_review_case(
            user_data,
            raw_ip,
            str(payload.get("tag") or ""),
            bundle,
            event_id,
            review_reason,
        )
        review_case_id = review_case.id
        bundle.case_id = review_case_id

    enforcement_result = await _apply_enforcement_if_needed(
        container,
        _remnawave_client(container),
        user_data,
        payload,
        bundle,
        rules,
    )
    return {
        "status": "processed",
        "event_id": event_id,
        "review_case_id": review_case_id,
        "bundle": bundle.to_dict(),
        "review_reason": review_reason,
        "enforcement": enforcement_result,
    }


def register_module(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    metadata_payload = payload.get("metadata")
    module = container.store.register_module(
        str(payload.get("module_id") or ""),
        token,
        module_name=str(payload.get("module_name") or ""),
        version=str(payload.get("version") or ""),
        protocol_version=protocol_version,
        metadata=dict(metadata_payload) if isinstance(metadata_payload, dict) else None,
        config_revision_applied=int(payload.get("config_revision_applied") or 0),
        auto_create=False,
    )
    return {
        "protocol_version": protocol_version,
        "module": module,
        "config": get_module_config(container, module)["config"],
    }


def record_module_heartbeat(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    module = container.store.authenticate_module(str(payload.get("module_id") or ""), token)
    updated = container.store.record_module_heartbeat(
        module["module_id"],
        status=str(payload.get("status") or "online"),
        version=str(payload.get("version") or module.get("version") or ""),
        protocol_version=protocol_version,
        config_revision_applied=int(payload.get("config_revision_applied") or 0),
        details=dict(payload.get("details") or {}),
    )
    return {
        "protocol_version": protocol_version,
        "module": updated,
        "desired_config_revision": container.store.get_live_rules_state()["revision"],
    }


def get_module_config(container: APIContainer, module: dict[str, Any] | None) -> dict[str, Any]:
    rules_state = container.store.get_live_rules_state()
    settings = rules_state["rules"].get("settings", {})
    return {
        "config": {
            "protocol_version": PROTOCOL_VERSION,
            "config_revision": rules_state["revision"],
            "updated_at": rules_state["updated_at"],
            "rules": rules_state["rules"],
            "module_runtime": _module_runtime(settings),
        },
        "module": module,
    }


async def ingest_module_events(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    module = container.store.authenticate_module(str(payload.get("module_id") or ""), token)
    accepted = 0
    duplicates = 0
    processed = 0
    review_cases = 0
    results: list[dict[str, Any]] = []

    for raw_item in list(payload.get("items") or []):
        item = dict(raw_item)
        uid = _event_uid(module["module_id"], item)
        if not container.store.ingest_raw_event(
            module["module_id"],
            module["module_name"],
            uid,
            str(item.get("occurred_at") or ""),
            {**item, "event_uid": uid},
        ):
            duplicates += 1
            results.append({"event_uid": uid, "status": "duplicate"})
            continue

        accepted += 1
        processed_result = await _process_module_event(container, module, {**item, "event_uid": uid})
        await asyncio.to_thread(
            container.store.mark_raw_event_processed,
            uid,
            analysis_event_id=processed_result.get("event_id"),
            review_case_id=processed_result.get("review_case_id"),
        )
        processed += 1
        if processed_result.get("review_case_id"):
            review_cases += 1
        results.append({"event_uid": uid, **processed_result})

    return {
        "protocol_version": protocol_version,
        "module_id": module["module_id"],
        "accepted": accepted,
        "duplicates": duplicates,
        "processed": processed,
        "review_cases": review_cases,
        "config_revision": container.store.get_live_rules_state()["revision"],
        "results": results,
    }


def list_modules(container: APIContainer) -> dict[str, Any]:
    modules = container.store.list_modules()
    return {
        "items": modules,
        "count": len(modules),
    }


def create_managed_module(container: APIContainer, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _module_metadata_from_payload(payload)
    try:
        token = secrets.token_urlsafe(32)
        token_ciphertext = encrypt_module_token(_module_secret_key(container), token)
    except ModuleSecretError as exc:
        raise ValueError(str(exc)) from exc
    module = container.store.create_managed_module(
        _generate_module_id(container),
        token,
        token_ciphertext,
        module_name=normalized["module_name"],
        protocol_version=PROTOCOL_VERSION,
        metadata=normalized["metadata"],
    )
    return {
        "module": module,
        "install": {
            **_module_install_payload(container, module),
            "module_token": token,
        },
    }


def get_module_detail(container: APIContainer, module_id: str) -> dict[str, Any]:
    module = container.store.get_module(module_id)
    if not module:
        raise ValueError("Module is not registered")
    return _module_detail_response(container, module)


def update_module_detail(container: APIContainer, module_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _module_metadata_from_payload(payload)
    module = container.store.update_managed_module(
        module_id,
        module_name=normalized["module_name"],
        metadata=normalized["metadata"],
    )
    return _module_detail_response(container, module)


def reveal_module_token(container: APIContainer, module_id: str) -> dict[str, Any]:
    try:
        token = decrypt_module_token(
            _module_secret_key(container),
            container.store.get_module_token_ciphertext(module_id),
        )
    except ModuleSecretError as exc:
        raise ValueError(str(exc)) from exc
    return {"module_id": module_id, "module_token": token}
