from __future__ import annotations

from typing import Any, Mapping


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def coerce_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_review_identity_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(payload or {})
    raw_uuid = clean_text(normalized.get("uuid"))
    if normalized.get("system_id") in (None, "") and raw_uuid and raw_uuid.isdigit():
        normalized["system_id"] = int(raw_uuid)
        normalized["uuid"] = None
    telegram_id = normalized.get("telegram_id")
    if telegram_id in (None, "") and normalized.get("telegramId") not in (None, ""):
        normalized["telegram_id"] = clean_text(normalized.get("telegramId"))
    return normalized


def subject_key_from_identity(
    identity: Mapping[str, Any] | None,
    *,
    ip: str | None = None,
) -> str:
    normalized = normalize_review_identity_payload(identity)
    telegram_id = clean_text(normalized.get("telegram_id") or normalized.get("telegramId"))
    if telegram_id:
        return f"tg:{telegram_id}"
    system_id = coerce_optional_int(normalized.get("system_id") if "system_id" in normalized else normalized.get("id"))
    if system_id is not None:
        return f"sys:{system_id}"
    uuid = clean_text(normalized.get("uuid"))
    if uuid:
        return f"uuid:{uuid.lower()}"
    username = clean_text(normalized.get("username")).lower()
    if username:
        return f"user:{username}"
    raw_ip = clean_text(ip or normalized.get("ip"))
    if raw_ip:
        return f"ip:{raw_ip}"
    return "anonymous:unknown"


def device_key_from_identity(identity: Mapping[str, Any] | None) -> str:
    normalized = normalize_review_identity_payload(identity)
    return clean_text(
        normalized.get("client_device_id")
        or normalized.get("device_id")
        or normalized.get("deviceId")
    )


def device_display_from_identity(identity: Mapping[str, Any] | None) -> str:
    normalized = normalize_review_identity_payload(identity)
    label = clean_text(
        normalized.get("client_device_label")
        or normalized.get("device_label")
        or normalized.get("deviceLabel")
    )
    if label:
        return label
    os_family = clean_text(
        normalized.get("client_os_family")
        or normalized.get("os_family")
        or normalized.get("osFamily")
    )
    app_name = clean_text(
        normalized.get("client_app_name")
        or normalized.get("app_name")
        or normalized.get("appName")
    )
    if os_family and app_name:
        return f"{os_family} / {app_name}"
    if os_family:
        return os_family
    if app_name:
        return app_name
    return device_key_from_identity(normalized)


def build_review_scope(
    identity: Mapping[str, Any] | None,
    *,
    ip: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_review_identity_payload(identity)
    primary_ip = clean_text(ip or normalized.get("ip"))
    device_key = device_key_from_identity(normalized)
    device_display = device_display_from_identity(normalized)
    if device_key and primary_ip:
        normalized_device_key = device_key.lower()
        return {
            "scope_type": "ip_device",
            "case_scope_key": f"device:{normalized_device_key}|ip:{primary_ip}",
            "device_scope_key": f"device:{normalized_device_key}",
            "target_ip": primary_ip,
            "client_device_id": device_key,
            "client_device_label": device_display or None,
        }
    if primary_ip:
        return {
            "scope_type": "ip_only",
            "case_scope_key": f"ip:{primary_ip}",
            "device_scope_key": f"ip:{primary_ip}",
            "target_ip": primary_ip,
            "client_device_id": None,
            "client_device_label": None,
        }
    return {
        "scope_type": "ip_only",
        "case_scope_key": "ip:unknown",
        "device_scope_key": "ip:unknown",
        "target_ip": "",
        "client_device_id": None,
        "client_device_label": None,
    }


def provider_summary_from_signal_flags(signal_flags: Mapping[str, Any] | None) -> dict[str, Any]:
    provider_evidence = {}
    if isinstance(signal_flags, Mapping):
        candidate = signal_flags.get("provider_evidence")
        if isinstance(candidate, Mapping):
            provider_evidence = candidate
    return {
        "provider_key": clean_text(provider_evidence.get("provider_key")).lower() or None,
        "provider_classification": clean_text(provider_evidence.get("provider_classification")).lower() or "unknown",
        "provider_service_hint": clean_text(provider_evidence.get("service_type_hint")).lower() or "unknown",
        "provider_conflict": bool(provider_evidence.get("service_conflict")),
        "provider_review_recommended": bool(provider_evidence.get("review_recommended")),
    }
