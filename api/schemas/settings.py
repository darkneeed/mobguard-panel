from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SettingsSectionUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)
    lists: dict[str, list[Any]] = Field(default_factory=dict)
    env: dict[str, Any] = Field(default_factory=dict)
    revision: Optional[int] = None
    updated_at: Optional[str] = None
