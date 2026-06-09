from __future__ import annotations

import asyncio
import aiohttp
import json
import logging
import re
from datetime import datetime, timedelta
from collections import Counter
from typing import Any

logger = logging.getLogger("asn_lookup")

def parse_asn_from_str(s: Any) -> int | None:
    if not s:
        return None
    if isinstance(s, int):
        return s
    match = re.search(r'AS(\d+)', str(s), re.IGNORECASE)
    if match:
        return int(match.group(1))
    try:
        return int(s)
    except ValueError:
        return None

def clean_isp_name(org: str) -> str | None:
    if not org:
        return None
    org_str = str(org)
    name = re.sub(r'^AS\d+\s+', '', org_str, flags=re.IGNORECASE).strip()
    return name or None

async def fetch_ipinfo(session: aiohttp.ClientSession, ip: str, token: str | None) -> dict | None:
    url = f"https://ipinfo.io/{ip}"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with session.get(url, headers=headers, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                org = data.get("org")
                return {
                    "asn": parse_asn_from_str(org),
                    "isp": clean_isp_name(org),
                    "country": data.get("country"),
                    "is_mobile": None,
                    "raw": data
                }
    except Exception as e:
        logger.warning(f"Fetch ipinfo failed: {e}")
    return None

async def fetch_ip_api(session: aiohttp.ClientSession, ip: str) -> dict | None:
    url = f"http://ip-api.com/json/{ip}?fields=49663"
    try:
        async with session.get(url, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "success":
                    as_field = data.get("as")
                    return {
                        "asn": parse_asn_from_str(as_field),
                        "isp": data.get("isp"),
                        "country": data.get("countryCode"),
                        "is_mobile": data.get("mobile"),
                        "raw": data
                    }
    except Exception as e:
        logger.warning(f"Fetch ip-api failed: {e}")
    return None

async def fetch_ipapi_co(session: aiohttp.ClientSession, ip: str) -> dict | None:
    url = f"https://ipapi.co/{ip}/json/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with session.get(url, headers=headers, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                if not data.get("error"):
                    return {
                        "asn": parse_asn_from_str(data.get("asn")),
                        "isp": data.get("org"),
                        "country": data.get("country_code"),
                        "is_mobile": None,
                        "raw": data
                    }
    except Exception as e:
        logger.warning(f"Fetch ipapi.co failed: {e}")
    return None

async def fetch_ipwho_is(session: aiohttp.ClientSession, ip: str) -> dict | None:
    url = f"https://ipwho.is/{ip}"
    try:
        async with session.get(url, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    conn = data.get("connection", {})
                    return {
                        "asn": parse_asn_from_str(conn.get("asn")),
                        "isp": conn.get("isp") or conn.get("org"),
                        "country": data.get("country_code"),
                        "is_mobile": None,
                        "raw": data
                    }
    except Exception as e:
        logger.warning(f"Fetch ipwho.is failed: {e}")
    return None

async def fetch_ip_sb(session: aiohttp.ClientSession, ip: str) -> dict | None:
    url = f"https://api.ip.sb/geoip/{ip}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with session.get(url, headers=headers, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {
                    "asn": parse_asn_from_str(data.get("asn")),
                    "isp": data.get("isp") or data.get("organization"),
                    "country": data.get("country_code"),
                    "is_mobile": None,
                    "raw": data
                }
    except Exception as e:
        logger.warning(f"Fetch ip.sb failed: {e}")
    return None

async def lookup_ip_multi_source(
    ip: str,
    env_values: dict,
    rules: dict,
    conn,
    force: bool = False
) -> dict:
    # 0. Ensure table exists
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS asn_lookup_cache (
            ip TEXT PRIMARY KEY,
            asn INTEGER,
            isp TEXT,
            country TEXT,
            is_mobile INTEGER,  -- 0/1/NULL
            cached_at TEXT,     -- ISO datetime
            expires_at TEXT,    -- ISO datetime
            sources_count INTEGER,
            sources_raw TEXT
        )
        """
    )
    conn.commit()

    now = datetime.utcnow()
    
    # 1. Check cache
    if not force:
        row = conn.execute(
            "SELECT asn, isp, country, is_mobile, cached_at, expires_at, sources_count FROM asn_lookup_cache WHERE ip = ?",
            (ip,)
        ).fetchone()
        if row:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at > now:
                asn = row["asn"]
                isp = row["isp"]
                
                # Determine network type
                isp_lower = (isp or "").lower()
                is_datacenter = any(kw.lower() in isp_lower for kw in rules.get("exclude_isp_keywords", []))
                is_home_isp = any(kw.lower() in isp_lower for kw in rules.get("home_isp_keywords", []))
                
                is_mobile_val = bool(row["is_mobile"]) if row["is_mobile"] is not None else None
                
                if is_mobile_val:
                    network_type = "mobile"
                elif is_datacenter:
                    network_type = "datacenter"
                elif is_home_isp:
                    network_type = "home"
                elif asn in rules.get("pure_mobile_asns", []):
                    network_type = "mobile"
                elif asn in rules.get("pure_home_asns", []):
                    network_type = "home"
                else:
                    network_type = "unknown"
                    
                in_lists = {
                    "pure_mobile_asns": asn in rules.get("pure_mobile_asns", []),
                    "pure_home_asns": asn in rules.get("pure_home_asns", []),
                    "mixed_asns": asn in rules.get("mixed_asns", []),
                    "exclude_isp_keywords": is_datacenter
                }
                
                return {
                    "ip": ip,
                    "asn": asn,
                    "isp": isp,
                    "country": row["country"],
                    "is_mobile": is_mobile_val,
                    "network_type": network_type,
                    "sources_count": row["sources_count"],
                    "in_lists": in_lists,
                    "cached": True,
                    "cached_at": row["cached_at"]
                }

    # 2. Parallel fetch
    ipinfo_token = env_values.get("IPINFO_TOKEN")
    
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            fetch_ipinfo(session, ip, ipinfo_token),
            fetch_ip_api(session, ip),
            fetch_ipapi_co(session, ip),
            fetch_ipwho_is(session, ip),
            fetch_ip_sb(session, ip)
        )
        
    keys = ["ipinfo", "ip_api", "ipapi_co", "ipwho_is", "ip_sb"]
    prioritized_results = []
    sources_raw = {}
    
    for i, res in enumerate(results):
        key = keys[i]
        if res:
            prioritized_results.append(res)
            sources_raw[key] = res["raw"]
        else:
            sources_raw[key] = None
            
    sources_count = len(prioritized_results)
    if sources_count == 0:
        return {
            "ip": ip,
            "asn": None,
            "isp": None,
            "country": None,
            "is_mobile": None,
            "network_type": "unknown",
            "sources_count": 0,
            "in_lists": {
                "pure_mobile_asns": False,
                "pure_home_asns": False,
                "mixed_asns": False,
                "exclude_isp_keywords": False
            },
            "cached": False,
            "cached_at": None
        }

    # 3. Consensus
    def get_consensus_value(field: str):
        values = [r[field] for r in prioritized_results if r[field] is not None]
        if not values:
            return None
        counts = Counter(values)
        max_count = max(counts.values())
        candidates = [val for val, count in counts.items() if count == max_count]
        if len(candidates) == 1:
            return candidates[0]
        # Tie-breaker: order of priority
        for r in prioritized_results:
            if r[field] in candidates:
                return r[field]
        return candidates[0]

    asn = get_consensus_value("asn")
    isp = get_consensus_value("isp")
    country = get_consensus_value("country")
    
    # is_mobile is only from ip-api (index 1 of results)
    is_mobile_val = None
    if results[1] and results[1]["is_mobile"] is not None:
        is_mobile_val = bool(results[1]["is_mobile"])

    # 4. Network type
    isp_lower = (isp or "").lower()
    is_datacenter = any(kw.lower() in isp_lower for kw in rules.get("exclude_isp_keywords", []))
    is_home_isp = any(kw.lower() in isp_lower for kw in rules.get("home_isp_keywords", []))
    
    if is_mobile_val:
        network_type = "mobile"
    elif is_datacenter:
        network_type = "datacenter"
    elif is_home_isp:
        network_type = "home"
    elif asn in rules.get("pure_mobile_asns", []):
        network_type = "mobile"
    elif asn in rules.get("pure_home_asns", []):
        network_type = "home"
    else:
        network_type = "unknown"

    # 5. Save to Cache
    cached_at_str = now.isoformat()
    expires_at_str = (now + timedelta(days=90)).isoformat()
    is_mobile_int = 1 if is_mobile_val else (0 if is_mobile_val is False else None)
    
    conn.execute(
        """
        INSERT OR REPLACE INTO asn_lookup_cache (
            ip, asn, isp, country, is_mobile, cached_at, expires_at, sources_count, sources_raw
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ip,
            asn,
            isp,
            country,
            is_mobile_int,
            cached_at_str,
            expires_at_str,
            sources_count,
            json.dumps(sources_raw, ensure_ascii=False)
        )
    )
    conn.commit()

    in_lists = {
        "pure_mobile_asns": asn in rules.get("pure_mobile_asns", []),
        "pure_home_asns": asn in rules.get("pure_home_asns", []),
        "mixed_asns": asn in rules.get("mixed_asns", []),
        "exclude_isp_keywords": is_datacenter
    }

    return {
        "ip": ip,
        "asn": asn,
        "isp": isp,
        "country": country,
        "is_mobile": is_mobile_val,
        "network_type": network_type,
        "sources_count": sources_count,
        "in_lists": in_lists,
        "cached": False,
        "cached_at": cached_at_str
    }
