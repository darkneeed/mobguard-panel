from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LocalLoginRequest(BaseModel):
    username: str
    password: str


class TelegramVerifyRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
