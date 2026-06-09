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
    module_name: str | None = None,
    _: dict[str, Any] = Depends(require_permission(PERMISSION_MODULES_READ)),
    container=Depends(get_container),
) -> dict[str, Any]:
    from ..services.runtime_state import panel_client
    client = panel_client(container)
    inbounds = client.get_inbounds()
    
    if not inbounds:
        return {"inbounds": [], "available": False}
        
    if module_name:
        module_name_clean = module_name.strip().lower()
        if module_name_clean:
            try:
                profiles_payload = client._request("GET", "/api/config-profiles")
                if profiles_payload:
                    response_part = profiles_payload.get("response", profiles_payload)
                    profiles = response_part.get("configProfiles", response_part) if isinstance(response_part, dict) else []
                    
                    matching_uuid = None
                    for p in profiles:
                        p_name = str(p.get("name") or "").strip().lower()
                        if module_name_clean == p_name or p_name in module_name_clean or module_name_clean in p_name:
                            matching_uuid = p.get("uuid")
                            break
                        for n in p.get("nodes", []):
                            n_name = str(n.get("name") or "").strip().lower()
                            if module_name_clean == n_name or n_name in module_name_clean or module_name_clean in n_name:
                                matching_uuid = p.get("uuid")
                                break
                        if matching_uuid:
                            break
                            
                    if matching_uuid:
                        filtered = [item for item in inbounds if item.get("profileUuid") == matching_uuid]
                        if filtered:
                            inbounds = filtered
            except Exception:
                pass
                
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
