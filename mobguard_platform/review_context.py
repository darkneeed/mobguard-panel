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
