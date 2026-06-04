from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from fastapi import HTTPException

from ..context import APIContainer


def _runtime_settings(container: APIContainer) -> dict[str, Any]:
    settings = container.runtime.config.get("settings", {})
    return settings if isinstance(settings, dict) else {}


def _client_config(container: APIContainer) -> tuple[str, str, int]:
    settings = _runtime_settings(container)
    base_url = str(settings.get("bedolaga_api_url") or "").strip().rstrip("/")
    token = str(settings.get("bedolaga_api_token") or "").strip()
    timeout_seconds = int(settings.get("bedolaga_timeout_seconds") or 12)
    return base_url, token, max(timeout_seconds, 1)


def _perform_request(
    base_url: str,
    token: str,
    timeout_seconds: int,
    *,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url_path = "/" + str(path or "").lstrip("/")
    url = f"{base_url}{url_path}"
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-API-Key"] = token
    req = request.Request(url, data=body, method=method.upper(), headers=headers)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"raw": raw}
            return {
                "ok": True,
                "status": int(getattr(response, "status", 200)),
                "url": url,
                "data": parsed,
            }
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "status": int(exc.code), "url": url, "error": raw[:4000]}
    except error.URLError as exc:
        return {"ok": False, "status": 0, "url": url, "error": str(exc.reason)}


def get_bedolaga_overview(container: APIContainer) -> dict[str, Any]:
    base_url, token, timeout_seconds = _client_config(container)
    if not base_url:
        return {
            "enabled": False,
            "base_url": "",
            "metrics": {},
            "clients": [],
            "errors": ["bedolaga_api_url is not configured"],
        }
    metrics = _perform_request(base_url, token, timeout_seconds, path="/stats")
    clients = _perform_request(base_url, token, timeout_seconds, path="/users?limit=20")
    errors: list[str] = []
    if not metrics.get("ok"):
        errors.append(f"metrics: {metrics.get('error') or metrics.get('status')}")
    if not clients.get("ok"):
        errors.append(f"clients: {clients.get('error') or clients.get('status')}")
    return {
        "enabled": True,
        "base_url": base_url,
        "metrics": metrics.get("data", {}),
        "clients": clients.get("data", []),
        "errors": errors,
    }


def proxy_bedolaga_action(
    container: APIContainer,
    *,
    path: str,
    method: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url, token, timeout_seconds = _client_config(container)
    if not base_url:
        raise HTTPException(status_code=409, detail="Bedolaga API is not configured")
    result = _perform_request(
        base_url,
        token,
        timeout_seconds,
        path=path,
        method=method,
        payload=payload,
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=f"Bedolaga upstream failed: {result.get('status')} {result.get('error')}",
        )
    return result
