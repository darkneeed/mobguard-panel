from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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
