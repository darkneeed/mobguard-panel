from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ReviewResolutionRequest(BaseModel):
    resolution: str
    note: str = ""


class RulesUpdateRequest(BaseModel):
    rules: dict[str, Any] = Field(default_factory=dict)
    revision: Optional[int] = None
    updated_at: Optional[str] = None
