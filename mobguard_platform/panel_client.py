from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class PanelClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.token)

    def get_user_data(self, identifier: str) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None

        str_id = str(identifier).strip()
        endpoints: list[str]
        if UUID_PATTERN.fullmatch(str_id):
            endpoints = [
                f"/api/users/{quote(str_id)}",
                f"/api/users/by-short-uuid/{quote(str_id)}",
            ]
        elif str_id.isdigit():
            endpoints = [
                f"/api/users/by-id/{quote(str_id)}",
                f"/api/users/by-telegram-id/{quote(str_id)}",
            ]
        else:
            endpoints = [
                f"/api/users/by-username/{quote(str_id)}",
                f"/api/users/by-short-uuid/{quote(str_id)}",
                f"/api/users/{quote(str_id)}",
            ]

        for endpoint in endpoints:
            payload = self._request("GET", endpoint)
            user = self._extract_user(payload)
            if user:
                return user
        return None

    def toggle_user(self, uuid: str, enable: bool) -> bool:
        if not self.enabled:
            return False
        action = "enable" if enable else "disable"
        payload = self._request("POST", f"/api/users/{quote(uuid)}/actions/{action}", body={})
        return payload is not None

    def _request(self, method: str, endpoint: str, body: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
        url = f"{self.base_url}{endpoint}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(url, headers=headers, method=method, data=data)
        try:
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None

    def _extract_user(self, payload: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not payload:
            return None
        response = payload.get("response", payload)
        if isinstance(response, list):
            return response[0] if response else None
        if isinstance(response, dict):
            return response
        return None
