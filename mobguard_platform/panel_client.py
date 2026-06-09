from __future__ import annotations

import json
import re
import time
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timedelta


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


class RemnawaveClient:
    USER_CACHE_TTL_SECONDS = 15.0
    NEGATIVE_USER_CACHE_TTL_SECONDS = 10.0
    DEVICE_CACHE_TTL_SECONDS = 30.0
    TRAFFIC_CACHE_TTL_SECONDS = 30.0
    NODES_CACHE_TTL_SECONDS = 20.0

    def __init__(self, base_url: str, token: str):
        self.base_url = self._normalize_base_url(base_url)
        self.token = token
        self.last_error: Optional[str] = None
        self._internal_squad_uuid_cache: dict[str, str] = {}
        self._internal_squads_cache: list[dict[str, Any]] | None = None
        self._user_cache: dict[str, tuple[float, Any]] = {}
        self._devices_cache: dict[str, tuple[float, Any]] = {}
        self._traffic_cache: dict[str, tuple[float, Any]] = {}
        self._nodes_cache: tuple[float, list[dict[str, Any]]] | None = None

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = str(base_url or "").strip().rstrip("/")
        if normalized.lower().endswith("/api"):
            return normalized[:-4].rstrip("/")
        return normalized

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.token)

    def _normalized_lookup_key(self, identifier: str) -> str:
        normalized = str(identifier or "").strip()
        if normalized.isdigit():
            return normalized
        return normalized.lower()

    def _typed_lookup_key(self, lookup_type: str, identifier: str) -> str:
        normalized = self._normalized_lookup_key(identifier)
        if not normalized:
            return ""
        return f"{lookup_type}:{normalized}"

    def _clone_cached_value(self, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.loads(json.dumps(value, ensure_ascii=False))
        return value

    def _cache_get(self, cache: dict[str, tuple[float, Any]], key: str) -> tuple[bool, Any]:
        entry = cache.get(key)
        if entry is None:
            return False, None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            cache.pop(key, None)
            return False, None
        return True, self._clone_cached_value(value)

    def _cache_set(self, cache: dict[str, tuple[float, Any]], key: str, value: Any, ttl_seconds: float) -> None:
        normalized_key = self._normalized_lookup_key(key)
        if not normalized_key:
            return
        cache[normalized_key] = (time.monotonic() + max(float(ttl_seconds), 0.0), self._clone_cached_value(value))

    def _cache_user_lookup(
        self,
        identifier: str,
        user: Optional[dict[str, Any]],
        *,
        lookup_type: str = "auto",
    ) -> None:
        ttl = self.USER_CACHE_TTL_SECONDS if user else self.NEGATIVE_USER_CACHE_TTL_SECONDS
        self._cache_set(self._user_cache, self._typed_lookup_key(lookup_type, identifier), user, ttl)

    def _should_hydrate_user_profile(self, lookup_type: str, identifier: str) -> bool:
        normalized = str(identifier or "").strip()
        if lookup_type == "username":
            return True
        if lookup_type != "auto":
            return False
        if not normalized or normalized.isdigit() or UUID_PATTERN.fullmatch(normalized):
            return False
        return True

    def _hydrate_user_profile(self, user: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not isinstance(user, dict):
            return None
        hydrated = dict(user)
        uuid_value = str(hydrated.get("uuid") or "").strip()
        if not uuid_value:
            return hydrated
        has_id = hydrated.get("id") not in (None, "")
        has_telegram = hydrated.get("telegramId") not in (None, "")
        if has_telegram:
            return hydrated
        payload = self._request("GET", f"/api/users/{quote(uuid_value)}")
        detailed = self._extract_user(payload)
        if not isinstance(detailed, dict):
            return hydrated
        for key, value in detailed.items():
            if hydrated.get(key) in (None, "") and value not in (None, ""):
                hydrated[key] = value
        return hydrated

    def _resolve_user_candidates(self, identifier: str, *, lookup_type: str = "auto") -> list[dict[str, Any]]:
        normalized = str(identifier or "").strip()
        if not normalized:
            return []
        if lookup_type == "uuid":
            return [{"uuid": normalized}]
        if lookup_type == "system_id":
            return [{"id": int(normalized)}] if normalized.isdigit() else []
        if lookup_type == "telegram_id":
            return [{"telegramId": normalized}] if normalized.isdigit() else []
        if lookup_type == "username":
            return [{"username": normalized}]
        if lookup_type == "short_uuid":
            return [{"shortUuid": normalized}]
        if UUID_PATTERN.fullmatch(normalized):
            return [{"uuid": normalized}]
        if normalized.isdigit():
            return [{"id": int(normalized)}]
        return [{"username": normalized}, {"shortUuid": normalized}]

    def _user_lookup_endpoints(self, str_id: str, *, lookup_type: str) -> list[str]:
        if lookup_type == "uuid":
            return [f"/api/users/{quote(str_id)}", f"/api/users/by-short-uuid/{quote(str_id)}"]
        if lookup_type == "system_id":
            return [f"/api/users/by-id/{quote(str_id)}"]
        if lookup_type == "telegram_id":
            return [f"/api/users/by-telegram-id/{quote(str_id)}"]
        if lookup_type == "username":
            return [f"/api/users/by-username/{quote(str_id)}", f"/api/users/{quote(str_id)}"]
        if lookup_type == "short_uuid":
            return [f"/api/users/by-short-uuid/{quote(str_id)}", f"/api/users/{quote(str_id)}"]
        if UUID_PATTERN.fullmatch(str_id):
            return [
                f"/api/users/{quote(str_id)}",
                f"/api/users/by-short-uuid/{quote(str_id)}",
            ]
        if str_id.isdigit():
            return [
                f"/api/users/by-id/{quote(str_id)}",
                f"/api/users/by-telegram-id/{quote(str_id)}",
            ]
        return [
            f"/api/users/by-username/{quote(str_id)}",
            f"/api/users/by-short-uuid/{quote(str_id)}",
            f"/api/users/{quote(str_id)}",
        ]

    def _get_user_data_with_hint(self, identifier: str, *, lookup_type: str = "auto") -> Optional[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return None

        self.last_error = None
        str_id = str(identifier).strip()
        typed_lookup_key = self._typed_lookup_key(lookup_type, str_id)
        should_hydrate = self._should_hydrate_user_profile(lookup_type, str_id)
        cache_hit, cached_user = self._cache_get(self._user_cache, typed_lookup_key)
        if cache_hit:
            return cached_user

        for payload_body in self._resolve_user_candidates(str_id, lookup_type=lookup_type):
            payload = self._request("POST", "/api/users/resolve", body=payload_body)
            user = self._extract_user(payload)
            if should_hydrate:
                user = self._hydrate_user_profile(user)
            if user:
                self._cache_user(user)
                self._cache_user_lookup(str_id, user, lookup_type=lookup_type)
                return user

        for endpoint in self._user_lookup_endpoints(str_id, lookup_type=lookup_type):
            payload = self._request("GET", endpoint)
            user = self._extract_user(payload)
            if should_hydrate:
                user = self._hydrate_user_profile(user)
            if user:
                self._cache_user(user)
                self._cache_user_lookup(str_id, user, lookup_type=lookup_type)
                return user
        self._cache_user_lookup(str_id, None, lookup_type=lookup_type)
        return None

    def get_user_data(self, identifier: str) -> Optional[dict[str, Any]]:
        return self._get_user_data_with_hint(identifier, lookup_type="auto")

    def get_user_data_by_uuid(self, uuid: str) -> Optional[dict[str, Any]]:
        return self._get_user_data_with_hint(uuid, lookup_type="uuid")

    def get_user_data_by_system_id(self, system_id: int | str) -> Optional[dict[str, Any]]:
        return self._get_user_data_with_hint(str(system_id), lookup_type="system_id")

    def get_user_data_by_telegram_id(self, telegram_id: int | str) -> Optional[dict[str, Any]]:
        return self._get_user_data_with_hint(str(telegram_id), lookup_type="telegram_id")

    def get_user_data_by_username(self, username: str) -> Optional[dict[str, Any]]:
        return self._get_user_data_with_hint(username, lookup_type="username")

    def get_user_hwid_devices(self, user_uuid: str) -> list[dict[str, Any]]:
        normalized_uuid = str(user_uuid or "").strip()
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return []
        if not normalized_uuid:
            self.last_error = "User UUID is empty"
            return []

        self.last_error = None
        cache_hit, cached_devices = self._cache_get(self._devices_cache, normalized_uuid)
        if cache_hit:
            return cached_devices
        for endpoint in (
            f"/api/hwid/devices/{quote(normalized_uuid)}",
            f"/api/v2/users/{quote(normalized_uuid)}/hwid-devices",
        ):
            payload = self._request("GET", endpoint)
            devices = self._extract_devices(payload)
            if devices:
                self._cache_set(self._devices_cache, normalized_uuid, devices, self.DEVICE_CACHE_TTL_SECONDS)
                return devices
        self._cache_set(self._devices_cache, normalized_uuid, [], self.DEVICE_CACHE_TTL_SECONDS)
        return []

    def get_user_traffic_stats(
        self,
        user_uuid: str,
        *,
        start: str | None = None,
        end: str | None = None,
        top_nodes_limit: int = 50,
    ) -> Optional[dict[str, Any]]:
        normalized_uuid = str(user_uuid or "").strip()
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return None
        if not normalized_uuid:
            self.last_error = "User UUID is empty"
            return None

        cache_key = f"{normalized_uuid}|{start or ''}|{end or ''}|{max(int(top_nodes_limit), 1)}"
        cache_hit, cached_stats = self._cache_get(self._traffic_cache, cache_key)
        if cache_hit:
            return cached_stats

        now = datetime.utcnow()
        start_value = start or (now - timedelta(days=1)).strftime("%Y-%m-%d")
        end_value = end or (now + timedelta(days=1)).strftime("%Y-%m-%d")
        query = urlencode(
            {
                "start": start_value,
                "end": end_value,
                "topNodesLimit": max(int(top_nodes_limit), 1),
            }
        )
        payload = self._request("GET", f"/api/bandwidth-stats/users/{quote(normalized_uuid)}?{query}")
        if not payload:
            self._cache_set(self._traffic_cache, cache_key, None, self.TRAFFIC_CACHE_TTL_SECONDS)
            return None
        response = payload.get("response", payload)
        normalized_response = response if isinstance(response, dict) else None
        self._cache_set(self._traffic_cache, cache_key, normalized_response, self.TRAFFIC_CACHE_TTL_SECONDS)
        return normalized_response

    def list_internal_squads(self) -> list[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return []
        self.last_error = None
        if self._internal_squads_cache is not None:
            return [dict(item) for item in self._internal_squads_cache]
        payload = self._request("GET", "/api/internal-squads")
        response = payload.get("response", payload) if payload else None
        if isinstance(response, dict):
            squads = response.get("internalSquads", [])
        elif isinstance(response, list):
            squads = response
        else:
            squads = []
        result = [item for item in squads if isinstance(item, dict)]
        self._internal_squads_cache = [dict(item) for item in result]
        self._internal_squad_uuid_cache.update(
            {
                str(item.get("name", "")).strip(): str(item.get("uuid", "")).strip()
                for item in result
                if str(item.get("name", "")).strip() and str(item.get("uuid", "")).strip()
            }
        )
        return result

    def get_inbounds(self) -> list[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return []
        self.last_error = None
        payload = self._request("GET", "/api/config-profiles/inbounds")
        if not payload:
            return []
        response = payload.get("response", payload)
        if isinstance(response, dict):
            inbounds = response.get("inbounds", [])
            if isinstance(inbounds, list):
                return [item for item in inbounds if isinstance(item, dict)]
        elif isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        return []

    def get_system_stats(self) -> Optional[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return None
        self.last_error = None
        return self._request("GET", "/api/system/stats")

    def get_nodes_online_usage(self) -> list[dict[str, Any]]:
        if not self.enabled:
            self.last_error = "Panel client is disabled"
            return []
        self.last_error = None
        if self._nodes_cache is not None:
            expires_at, cached = self._nodes_cache
            if expires_at > time.monotonic():
                return [dict(item) for item in cached]
        payload = self._request("GET", "/api/nodes")
        response = payload.get("response", payload) if payload else None
        rows: list[dict[str, Any]]
        if isinstance(response, dict):
            items = response.get("items")
            rows = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        elif isinstance(response, list):
            rows = [item for item in response if isinstance(item, dict)]
        else:
            rows = []
        normalized: list[dict[str, Any]] = []
        for row in rows:
            online_raw = (
                row.get("users_online")
                if row.get("users_online") is not None
                else row.get("usersOnline")
            )
            try:
                users_online = max(int(online_raw or 0), 0)
            except (TypeError, ValueError):
                users_online = 0
            normalized.append(
                {
                    "uuid": str(row.get("uuid") or "").strip(),
                    "name": str(row.get("name") or "").strip(),
                    "users_online": users_online,
                }
            )
        self._nodes_cache = (
            time.monotonic() + self.NODES_CACHE_TTL_SECONDS,
            [dict(item) for item in normalized],
        )
        return normalized

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
            self._cache_user_lookup(uuid, user_copy, lookup_type="auto")
            self._cache_user_lookup(uuid, user_copy, lookup_type="uuid")
            if str(user_copy.get("username", "")).strip():
                self._cache_user_lookup(str(user_copy["username"]), user_copy, lookup_type="auto")
                self._cache_user_lookup(str(user_copy["username"]), user_copy, lookup_type="username")
            if user_copy.get("id") not in (None, ""):
                self._cache_user_lookup(str(user_copy["id"]), user_copy, lookup_type="auto")
                self._cache_user_lookup(str(user_copy["id"]), user_copy, lookup_type="system_id")
            if user_copy.get("telegramId") not in (None, ""):
                self._cache_user_lookup(str(user_copy["telegramId"]), user_copy, lookup_type="auto")
                self._cache_user_lookup(str(user_copy["telegramId"]), user_copy, lookup_type="telegram_id")
            short_uuid = str(user_copy.get("shortUuid", "")).strip()
            if short_uuid:
                self._cache_user_lookup(short_uuid, user_copy, lookup_type="auto")
                self._cache_user_lookup(short_uuid, user_copy, lookup_type="short_uuid")
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
            for key in ("user", "result"):
                nested = response.get(key)
                if isinstance(nested, dict):
                    return nested
            return response
        return None

    def _extract_devices(self, payload: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payload:
            return []
        response = payload.get("response", payload)
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        if isinstance(response, dict):
            devices = response.get("devices", [])
            if isinstance(devices, list):
                return [item for item in devices if isinstance(item, dict)]
        return []


PanelClient = RemnawaveClient
