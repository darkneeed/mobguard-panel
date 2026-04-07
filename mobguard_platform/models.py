from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DecisionReason:
    code: str
    source: str
    weight: int
    kind: str
    direction: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "source": self.source,
            "weight": self.weight,
            "kind": self.kind,
            "direction": self.direction,
            "message": self.message,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionReason":
        return cls(
            code=str(payload.get("code", "")),
            source=str(payload.get("source", "")),
            weight=int(payload.get("weight", 0)),
            kind=str(payload.get("kind", "soft")),
            direction=str(payload.get("direction", "NEUTRAL")),
            message=str(payload.get("message", "")),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass
class DecisionBundle:
    ip: str
    verdict: str
    confidence_band: str
    score: int
    reasons: list[DecisionReason] = field(default_factory=list)
    signal_flags: dict[str, Any] = field(default_factory=dict)
    asn: Optional[int] = None
    isp: str = "Unknown ISP"
    source: str = "rule_engine"
    punitive_eligible: bool = False
    log: list[str] = field(default_factory=list)
    details: str = ""
    event_id: Optional[int] = None
    case_id: Optional[int] = None

    def add_reason(
        self,
        code: str,
        source: str,
        weight: int,
        kind: str,
        direction: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.reasons.append(
            DecisionReason(
                code=code,
                source=source,
                weight=weight,
                kind=kind,
                direction=direction,
                message=message,
                metadata=metadata or {},
            )
        )

    @property
    def home_sources(self) -> set[str]:
        return {
            reason.source
            for reason in self.reasons
            if reason.direction == "HOME" and reason.weight < 0
        }

    @property
    def mobile_sources(self) -> set[str]:
        return {
            reason.source
            for reason in self.reasons
            if reason.direction == "MOBILE" and reason.weight > 0
        }

    @property
    def has_hard_home_reason(self) -> bool:
        return any(
            reason.direction == "HOME" and reason.kind == "hard" for reason in self.reasons
        )

    @property
    def reason_codes(self) -> list[str]:
        return [reason.code for reason in self.reasons]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ip": self.ip,
            "verdict": self.verdict,
            "confidence_band": self.confidence_band,
            "score": self.score,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "signal_flags": dict(self.signal_flags),
            "asn": self.asn,
            "isp": self.isp,
            "source": self.source,
            "punitive_eligible": self.punitive_eligible,
            "log": list(self.log),
            "details": self.details,
            "event_id": self.event_id,
            "case_id": self.case_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionBundle":
        return cls(
            ip=str(payload.get("ip", "")),
            verdict=str(payload.get("verdict", "UNSURE")),
            confidence_band=str(payload.get("confidence_band", "UNSURE")),
            score=int(payload.get("score", 0)),
            reasons=[
                DecisionReason.from_dict(item) for item in payload.get("reasons", [])
            ],
            signal_flags=dict(payload.get("signal_flags", {})),
            asn=payload.get("asn"),
            isp=str(payload.get("isp", "Unknown ISP")),
            source=str(payload.get("source", "rule_engine")),
            punitive_eligible=bool(payload.get("punitive_eligible", False)),
            log=list(payload.get("log", [])),
            details=str(payload.get("details", "")),
            event_id=payload.get("event_id"),
            case_id=payload.get("case_id"),
        )

    @classmethod
    def from_cache_record(cls, ip: str, cached: dict[str, Any]) -> "DecisionBundle":
        bundle_payload = cached.get("bundle")
        if isinstance(bundle_payload, dict):
            bundle = cls.from_dict(bundle_payload)
            if not bundle.ip:
                bundle.ip = ip
            return bundle

        details = str(cached.get("isp", cached.get("details", "Unknown ISP")))
        bundle = cls(
            ip=ip,
            verdict=str(cached.get("status", "UNSURE")),
            confidence_band=str(cached.get("confidence", "UNSURE")),
            score=int(cached.get("score", 0)),
            asn=cached.get("asn"),
            isp=details,
            details=details,
            punitive_eligible=False,
            log=list(cached.get("log", [])),
        )
        bundle.add_reason(
            code="cache_legacy",
            source="cache",
            weight=0,
            kind="soft",
            direction="NEUTRAL",
            message="Legacy cached decision restored without structured reasons",
        )
        return bundle

    def to_cache_payload(self) -> dict[str, Any]:
        return {
            "status": self.verdict,
            "confidence": self.confidence_band,
            "isp": self.isp,
            "details": self.details or self.isp,
            "asn": self.asn,
            "log": list(self.log),
            "score": self.score,
            "bundle": self.to_dict(),
        }


@dataclass
class ReviewCaseSummary:
    id: int
    status: str
    review_reason: str
    uuid: str
    username: str
    system_id: Optional[int]
    telegram_id: Optional[str]
    ip: str
    tag: str
    verdict: str
    confidence_band: str
    score: int
    isp: str
    asn: Optional[int]
    repeat_count: int
    reason_codes: list[str] = field(default_factory=list)
    updated_at: str = ""
    review_url: str = ""
