from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_FULL_ACCESS_SQUAD_NAME = "FULL"
DEFAULT_RESTRICTED_ACCESS_SQUAD_NAME = "MOBILE_BLOCKED"
DEFAULT_TRAFFIC_CAP_INCREMENT_GB = 10
DEFAULT_TRAFFIC_CAP_THRESHOLD_GB = 100
DEFAULT_TRAFFIC_LIMIT_STRATEGY = "NO_RESET"
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _normalized_squad_name(
    raw_settings: Mapping[str, Any] | None,
    key: str,
    default: str,
) -> str:
    settings = raw_settings or {}
    value = str(settings.get(key, default) or "").strip()
    return value or default


def get_full_access_squad_name(raw_settings: Mapping[str, Any] | None) -> str:
    return _normalized_squad_name(
        raw_settings,
        "full_access_squad_name",
        DEFAULT_FULL_ACCESS_SQUAD_NAME,
    )


def get_restricted_access_squad_name(raw_settings: Mapping[str, Any] | None) -> str:
    return _normalized_squad_name(
        raw_settings,
        "restricted_access_squad_name",
        DEFAULT_RESTRICTED_ACCESS_SQUAD_NAME,
    )


def _normalized_positive_int(
    raw_settings: Mapping[str, Any] | None,
    key: str,
    default: int,
) -> int:
    settings = raw_settings or {}
    try:
        value = int(settings.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def get_traffic_cap_increment_gb(raw_settings: Mapping[str, Any] | None) -> int:
    return _normalized_positive_int(
        raw_settings,
        "traffic_cap_increment_gb",
        DEFAULT_TRAFFIC_CAP_INCREMENT_GB,
    )


def get_traffic_cap_threshold_gb(raw_settings: Mapping[str, Any] | None) -> int:
    return _normalized_positive_int(
        raw_settings,
        "traffic_cap_threshold_gb",
        DEFAULT_TRAFFIC_CAP_THRESHOLD_GB,
    )


class PanelClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.last_error: Optional[str] = None
        self._internal_squad_uuid_cache: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.token)

    def get_user_data(self, identifier: str) -> Optional[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return None

        self.last_error = None
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
                self._cache_user(user)
                return user
        return None

    def list_internal_squads(self) -> list[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return []
        self.last_error = None
        payload = self._request("GET", "/api/internal-squads")
        response = payload.get("response", payload) if payload else None
        if isinstance(response, dict):
            squads = response.get("internalSquads", [])
        elif isinstance(response, list):
            squads = response
        else:
            squads = []
        result = [item for item in squads if isinstance(item, dict)]
        self._internal_squad_uuid_cache.update(
            {
                str(item.get("name", "")).strip(): str(item.get("uuid", "")).strip()
                for item in result
                if str(item.get("name", "")).strip() and str(item.get("uuid", "")).strip()
            }
        )
        return result

    def resolve_internal_squad_uuid(self, squad_name: str) -> Optional[str]:
        normalized_name = str(squad_name or "").strip()
        if not normalized_name:
            self.last_error = "Internal squad name is empty"
            return None

        cached = self._internal_squad_uuid_cache.get(normalized_name)
        if cached:
            self.last_error = None
            return cached

        for squad in self.list_internal_squads():
            if str(squad.get("name", "")).strip() == normalized_name:
                squad_uuid = str(squad.get("uuid", "")).strip()
                if squad_uuid:
                    self._internal_squad_uuid_cache[normalized_name] = squad_uuid
                    self.last_error = None
                    return squad_uuid

        self.last_error = f"Internal squad '{normalized_name}' was not found"
        return None

    def update_user_active_internal_squads(self, uuid: str, squad_uuids: list[str]) -> bool:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return False
        self.last_error = None
        payload = self.update_user_fields(uuid=uuid, activeInternalSquads=squad_uuids)
        return payload is not None

    def apply_access_squad(self, uuid: str, squad_name: str) -> bool:
        squad_uuid = self.resolve_internal_squad_uuid(squad_name)
        if not squad_uuid:
            return False
        return self.update_user_active_internal_squads(uuid, [squad_uuid])

    def update_user_fields(self, **fields: Any) -> Optional[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return None
        self.last_error = None
        payload = self._request("PATCH", "/api/users", body=fields)
        user = self._extract_user(payload)
        if user:
            self._cache_user(user)
        return payload

    def update_user_traffic_limit(
        self,
        uuid: str,
        traffic_limit_bytes: int,
        traffic_limit_strategy: str,
    ) -> bool:
        payload = self.update_user_fields(
            uuid=uuid,
            trafficLimitBytes=int(traffic_limit_bytes),
            trafficLimitStrategy=str(traffic_limit_strategy or DEFAULT_TRAFFIC_LIMIT_STRATEGY),
        )
        return payload is not None

    def _cache_user(self, user: dict[str, Any]) -> None:
        uuid = str(user.get("uuid", "")).strip()
        if uuid:
            user_copy = dict(user)
            self._internal_squad_uuid_cache.update(
                {
                    str(item.get("name", "")).strip(): str(item.get("uuid", "")).strip()
                    for item in user_copy.get("activeInternalSquads", [])
                    if isinstance(item, dict)
                    and str(item.get("name", "")).strip()
                    and str(item.get("uuid", "")).strip()
                }
            )

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
                self.last_error = None
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            self.last_error = f"HTTP {exc.code} for {endpoint}"
            return None
        except URLError as exc:
            self.last_error = f"URL error for {endpoint}: {exc.reason}"
            return None
        except TimeoutError:
            self.last_error = f"Timeout while calling {endpoint}"
            return None
        except json.JSONDecodeError:
            self.last_error = f"Invalid JSON response for {endpoint}"
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
