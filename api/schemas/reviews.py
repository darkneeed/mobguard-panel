from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ReviewResolutionRequest(BaseModel):
    resolution: str
    note: str = ""


class ReviewRecheckRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    module_id: Optional[str] = None
    review_reason: Optional[str] = None
    case_ids: list[int] = Field(default_factory=list, max_length=500)


class RulesUpdateRequest(BaseModel):
    rules: dict[str, Any] = Field(default_factory=dict)
    revision: Optional[int] = None
    updated_at: Optional[str] = None
