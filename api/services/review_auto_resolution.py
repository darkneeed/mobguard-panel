from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping


AUTO_REVIEW_ACTOR = "system:auto-review"
AUTO_REVIEW_NOTE_PREFIX = "auto review v1"


@dataclass(frozen=True, slots=True)
class AutoReviewMatch:
    rule_id: str
    resolution: str
    precision: float
    support: int
    audit_payload: dict[str, Any]

    def build_note(self) -> str:
        return (
            f"{AUTO_REVIEW_NOTE_PREFIX}: {self.rule_id} "
            f"precision={self.precision:.3f} support={self.support}"
        )


def _parse_opened_at(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _case_age_hours(opened_at: str | datetime | None, now: datetime) -> float | None:
    opened_dt = _parse_opened_at(opened_at)
    if opened_dt is None:
        return None
    return max((now - opened_dt).total_seconds() / 3600.0, 0.0)


def _activity_duration_hours(ongoing_duration_seconds: Any) -> float | None:
    if ongoing_duration_seconds in (None, ""):
        return None
    try:
        duration_seconds = float(ongoing_duration_seconds)
    except (TypeError, ValueError):
        return None
    if duration_seconds < 0:
        return None
    return duration_seconds / 3600.0


def _provider_key(provider_evidence: Mapping[str, Any] | None) -> str:
    if not isinstance(provider_evidence, Mapping):
        return ""
    return str(provider_evidence.get("provider_key") or "").strip().lower()


def _normalized_reason_codes(reason_codes: Iterable[str] | None) -> set[str]:
    return {
        str(code).strip()
        for code in (reason_codes or [])
        if str(code).strip()
    }


def _reason_metadata(reason: Any) -> dict[str, Any]:
    metadata = getattr(reason, "metadata", None)
    if isinstance(metadata, Mapping):
        return dict(metadata)
    if isinstance(reason, Mapping):
        candidate = reason.get("metadata")
        if isinstance(candidate, Mapping):
            return dict(candidate)
    return {}


def _extract_keywords(reasons: Iterable[Any] | None) -> set[str]:
    keywords: set[str] = set()
    for reason in reasons or []:
        metadata = _reason_metadata(reason)
        for keyword in metadata.get("keywords") or []:
            normalized = str(keyword or "").strip().lower()
            if normalized:
                keywords.add(normalized)
    return keywords


def _build_match(
    *,
    rule_id: str,
    precision: float,
    support: int,
    review_reason: str,
    provider_key: str,
    case_age_hours: float | None,
    activity_duration_hours: float | None,
    keywords: set[str],
    reason_codes: set[str],
) -> AutoReviewMatch:
    audit_payload: dict[str, Any] = {
        "rule_id": rule_id,
        "precision": precision,
        "support": support,
        "review_reason": review_reason,
        "provider_key": provider_key or None,
    }
    if case_age_hours is not None:
        audit_payload["case_age_hours"] = round(case_age_hours, 3)
    if activity_duration_hours is not None:
        audit_payload["activity_duration_hours"] = round(activity_duration_hours, 3)
    if keywords:
        audit_payload["keywords"] = sorted(keywords)
    if reason_codes:
        audit_payload["reason_codes"] = sorted(reason_codes)
    return AutoReviewMatch(
        rule_id=rule_id,
        resolution="MOBILE",
        precision=precision,
        support=support,
        audit_payload=audit_payload,
    )


def match_review_auto_resolution(
    *,
    opened_at: str | datetime | None,
    review_reason: str | None,
    provider_evidence: Mapping[str, Any] | None,
    reason_codes: Iterable[str] | None,
    reasons: Iterable[Any] | None,
    ongoing_duration_seconds: Any = None,
    now: datetime | None = None,
) -> AutoReviewMatch | None:
    current_time = now or datetime.utcnow().replace(microsecond=0)
    normalized_review_reason = str(review_reason or "").strip().lower()
    normalized_provider_key = _provider_key(provider_evidence)
    normalized_reason_codes = _normalized_reason_codes(reason_codes)
    keywords = _extract_keywords(reasons)
    age_hours = _case_age_hours(opened_at, current_time)
    activity_hours = _activity_duration_hours(ongoing_duration_seconds)

    if normalized_review_reason == "provider_conflict" and activity_hours is not None and activity_hours < 12:
        return _build_match(
            rule_id="mobile_short_provider_conflict",
            precision=0.991,
            support=114,
            review_reason=normalized_review_reason,
            provider_key=normalized_provider_key,
            case_age_hours=age_hours,
            activity_duration_hours=activity_hours,
            keywords=keywords,
            reason_codes=normalized_reason_codes,
        )

    if normalized_provider_key == "mts" and "pppoe" in keywords:
        return _build_match(
            rule_id="mobile_mts_pppoe_exception",
            precision=1.0,
            support=86,
            review_reason=normalized_review_reason,
            provider_key=normalized_provider_key,
            case_age_hours=age_hours,
            activity_duration_hours=activity_hours,
            keywords=keywords,
            reason_codes=normalized_reason_codes,
        )

    if normalized_review_reason == "provider_conflict" and "keyword_mobile" in normalized_reason_codes:
        return _build_match(
            rule_id="mobile_provider_conflict_keyword",
            precision=1.0,
            support=25,
            review_reason=normalized_review_reason,
            provider_key=normalized_provider_key,
            case_age_hours=age_hours,
            activity_duration_hours=activity_hours,
            keywords=keywords,
            reason_codes=normalized_reason_codes,
        )

    return None
