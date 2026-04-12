from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModuleRegisterRequest(BaseModel):
    module_id: str
    module_name: str = ""
    version: str = ""
    protocol_version: str = "v1"
    metadata: dict[str, Any] = Field(default_factory=dict)
    config_revision_applied: int = 0


class ModuleHeartbeatRequest(BaseModel):
    module_id: str
    status: str = "online"
    version: str = ""
    protocol_version: str = "v1"
    config_revision_applied: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class RawAccessEventRequest(BaseModel):
    event_uid: Optional[str] = None
    occurred_at: str
    log_offset: Optional[int] = None
    uuid: Optional[str] = None
    username: Optional[str] = None
    system_id: Optional[int] = None
    telegram_id: Optional[str] = None
    ip: str
    tag: Optional[str] = None


class EventBatchRequest(BaseModel):
    module_id: str
    protocol_version: str = "v1"
    items: list[RawAccessEventRequest] = Field(default_factory=list)


class ModuleProvisioningRequest(BaseModel):
    module_name: str
    host: str
    port: int
    access_log_path: str = "/var/log/remnanode/access.log"
    config_profiles: list[str] = Field(default_factory=list)
    provider: str = ""
    notes: str = ""


class ModuleTokenRevealRequest(BaseModel):
    pass
