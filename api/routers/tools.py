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
        try:
            def normalize_str(s) -> str:
                if not s:
                    return ""
                if isinstance(s, dict):
                    s = s.get("tag") or s.get("name") or s.get("uuid") or ""
                s = str(s).strip().lower()
                homoglyphs = {
                    'а': 'a', 'в': 'v', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i',
                    'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's',
                    'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
                    'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya', 'ь': '', 'ъ': ''
                }
                res = []
                for char in s:
                    res.append(homoglyphs.get(char, char))
                return "".join(res)

            def get_tokens(s: str) -> set[str]:
                import re
                norm = normalize_str(s)
                return set(re.findall(r'[a-z0-9]+', norm))

            module_name_clean = normalize_str(module_name)
            module_tokens = get_tokens(module_name)
            
            if module_name_clean:
                profiles_payload = client._request("GET", "/api/config-profiles")
                if profiles_payload:
                    response_part = profiles_payload.get("response", profiles_payload)
                    profiles = response_part.get("configProfiles", response_part) if isinstance(response_part, dict) else []
                    
                    profile_scores = []
                    for p in profiles:
                        p_uuid = p.get("uuid")
                        if not p_uuid:
                            continue
                        p_name = p.get("name") or ""
                        p_name_norm = normalize_str(p_name)
                        p_tokens = get_tokens(p_name)
                        
                        score = 0
                        
                        # Profile name matching
                        if p_name_norm == module_name_clean:
                            score += 100
                        elif p_name_norm in module_name_clean:
                            score += 50
                        elif module_name_clean in p_name_norm:
                            score += 50
                            
                        p_overlap = p_tokens.intersection(module_tokens)
                        score += 10 * len(p_overlap)
                        
                        # Nodes matching
                        for n in p.get("nodes", []):
                            n_name = n.get("name") or ""
                            n_name_norm = normalize_str(n_name)
                            n_tokens = get_tokens(n_name)
                            
                            if n_name_norm == module_name_clean:
                                score += 80
                            elif n_name_norm in module_name_clean:
                                score += 40
                            elif module_name_clean in n_name_norm:
                                score += 40
                                
                            n_overlap = n_tokens.intersection(module_tokens)
                            score += 8 * len(n_overlap)
                            
                        # Inbound tags matching
                        for tag in p.get("inbounds", []):
                            tag_norm = normalize_str(tag)
                            tag_tokens = get_tokens(tag)
                            
                            if tag_norm == module_name_clean:
                                score += 60
                            elif tag_norm in module_name_clean:
                                score += 30
                            elif module_name_clean in tag_norm:
                                score += 30
                                
                            tag_overlap = tag_tokens.intersection(module_tokens)
                            score += 5 * len(tag_overlap)
                            
                        if score > 0:
                            profile_scores.append((score, p_uuid))
                            
                    if profile_scores:
                        profile_scores.sort(key=lambda x: x[0], reverse=True)
                        matching_uuid = profile_scores[0][1]
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
