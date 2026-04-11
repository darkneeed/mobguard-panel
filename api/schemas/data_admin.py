from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UserBanRequest(BaseModel):
    minutes: int = Field(default=15, gt=0)


class UserStrikesRequest(BaseModel):
    action: str = Field(default="set")
    count: int = Field(default=1, ge=0)


class UserWarningsRequest(BaseModel):
    action: str = Field(default="clear")
    count: int = Field(default=1, ge=0)


class UserExemptRequest(BaseModel):
    kind: str
    enabled: bool = True


class UserTrafficCapRequest(BaseModel):
    gigabytes: int = Field(default=10, gt=0)


class OverrideUpsertRequest(BaseModel):
    decision: str
    ttl_days: int = Field(default=7, ge=1, le=3650)


class CachePatchRequest(BaseModel):
    status: Optional[str] = None
    confidence: Optional[str] = None
    details: Optional[str] = None
    asn: Optional[int] = None
    expires: Optional[str] = None
    log_json: Optional[str] = None
    bundle_json: Optional[str] = None


class LegacyLearningPatchRequest(BaseModel):
    decision: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=0)
