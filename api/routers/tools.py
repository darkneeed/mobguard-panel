from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_container, require_permission
from ..permissions import PERMISSION_RULES_READ, PERMISSION_MODULES_READ
from ..services.runtime_state import load_env_values
from ..services import asn_lookup as asn_lookup_service

router = APIRouter(prefix="/admin/tools", tags=["tools"])

@router.get("/remnawave-inbounds")
def get_remnawave_inbounds(
    _: dict[str, Any] = Depends(require_permission(PERMISSION_MODULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    from ..services.runtime_state import panel_client
    client = panel_client(container)
    inbounds = client.get_inbounds()
    return {"inbounds": inbounds, "available": bool(inbounds)}


class AsnLookupRequest(BaseModel):
    ip: str
    force: bool = False

@router.post("/asn-lookup")
async def asn_lookup(
    body: AsnLookupRequest,
    _: dict[str, Any] = Depends(require_permission(PERMISSION_RULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    env_values = load_env_values(container)
    live_state = container.store.get_live_rules_state()
    rules = live_state.get("rules", {})
    
    with container.store._connect() as conn:
        result = await asn_lookup_service.lookup_ip_multi_source(
            ip=body.ip,
            env_values=env_values,
            rules=rules,
            conn=conn,
            force=body.force
        )
    return result
