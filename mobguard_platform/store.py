from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from .models import DecisionBundle, ReviewCaseSummary
from .asn_sources import detect_asn_source
from .repositories.admin_security import AdminSecurityRepository
from .repositories.health import ServiceHealthRepository
from .repositories.modules_admin import ModuleAdminRepository
from .repositories.review_admin import ReviewAdminRepository
from .repositories.sessions import AdminSessionRepository
from .runtime import canonicalize_runtime_bound_settings
from .storage.sqlite import SQLiteStorage, is_sqlite_busy_error, is_sqlite_interrupted_error


EDITABLE_TOP_LEVEL_KEYS = {
    "pure_mobile_asns": int,
    "pure_home_asns": int,
    "mixed_asns": int,
    "allowed_isp_keywords": str,
    "home_isp_keywords": str,
    "exclude_isp_keywords": str,
    "admin_tg_ids": int,
    "moderator_tg_ids": int,
    "viewer_tg_ids": int,
    "exempt_tg_ids": int,
    "exempt_ids": int,
}

PROVIDER_CLASSIFICATION_ALIASES = {
    "mixed": "mixed",
    "mobile": "mobile",
    "home": "home",
    "pure_mobile": "mobile",
    "pure_home": "home",
}

LEGACY_EDITABLE_SETTING_ALIASES = {
    "mobile_score_threshold": "threshold_mobile",
}

EDITABLE_SETTINGS_KEYS = {
    "pure_asn_score": (int, float),
    "mixed_asn_score": (int, float),
    "ptr_home_penalty": (int, float),
    "mobile_kw_bonus": (int, float),
    "provider_mobile_marker_bonus": (int, float),
    "provider_home_marker_penalty": (int, float),
    "ip_api_mobile_bonus": (int, float),
    "pure_home_asn_penalty": (int, float),
    "concurrency_threshold": int,
    "churn_window_hours": int,
    "churn_mobile_threshold": int,
    "history_lookback_days": int,
    "history_min_gap_minutes": int,
    "history_mobile_same_subnet_min_distinct_ips": int,
    "history_mobile_bonus": (int, float),
    "history_home_same_ip_min_records": int,
    "history_home_same_ip_min_span_hours": (int, float),
    "history_home_penalty": (int, float),
    "lifetime_stationary_hours": (int, float),
    "subnet_mobile_ttl_days": int,
    "subnet_home_ttl_days": int,
    "subnet_mobile_min_evidence": int,
    "subnet_home_min_evidence": int,
    "score_subnet_mobile_bonus": (int, float),
    "score_subnet_home_penalty": (int, float),
    "score_churn_high_bonus": (int, float),
    "score_churn_medium_bonus": (int, float),
    "score_stationary_penalty": (int, float),
    "threshold_probable_home": (int, float),
    "threshold_probable_mobile": (int, float),
    "threshold_home": (int, float),
    "threshold_mobile": (int, float),
    "shadow_mode": bool,
    "probable_home_warning_only": bool,
    "auto_enforce_requires_hard_or_multi_signal": bool,
    "provider_conflict_review_only": bool,
    "review_ui_base_url": str,
    "learning_promote_asn_min_support": int,
    "learning_promote_asn_min_precision": (int, float),
    "learning_promote_combo_min_support": int,
    "learning_promote_combo_min_precision": (int, float),
    "live_rules_refresh_seconds": int,
    "db_cleanup_interval_minutes": int,
    "module_heartbeats_retention_days": int,
    "ingested_raw_events_retention_days": int,
    "ip_history_retention_days": int,
    "orphan_analysis_events_retention_days": int,
    "resolved_review_retention_days": int,
}

DEFAULT_SETTINGS = {
    "shadow_mode": True,
    "probable_home_warning_only": True,
    "auto_enforce_requires_hard_or_multi_signal": True,
    "provider_conflict_review_only": True,
    "review_ui_base_url": "",
    "provider_mobile_marker_bonus": 18,
    "provider_home_marker_penalty": -18,
    "score_subnet_home_penalty": 0,
    "history_lookback_days": 14,
    "history_min_gap_minutes": 30,
    "history_mobile_same_subnet_min_distinct_ips": 8,
    "history_mobile_bonus": 40,
    "history_home_same_ip_min_records": 5,
    "history_home_same_ip_min_span_hours": 24,
    "history_home_penalty": -25,
    "learning_promote_asn_min_support": 10,
    "learning_promote_asn_min_precision": 0.95,
    "learning_promote_combo_min_support": 5,
    "learning_promote_combo_min_precision": 0.90,
    "live_rules_refresh_seconds": 15,
    "db_cleanup_interval_minutes": 30,
    "module_heartbeats_retention_days": 14,
    "ingested_raw_events_retention_days": 30,
    "ip_history_retention_days": 30,
    "orphan_analysis_events_retention_days": 30,
    "resolved_review_retention_days": 90,
}


logger = logging.getLogger(__name__)
LOW_PRIORITY_SQLITE_TIMEOUT_SECONDS = 1
LOW_PRIORITY_SQLITE_BUSY_TIMEOUT_MS = 1000
FAST_READ_SQLITE_TIMEOUT_SECONDS = 0.5
FAST_READ_SQLITE_BUSY_TIMEOUT_MS = 500
FAST_READ_SQLITE_QUERY_LIMIT_MS = 250
READ_MODEL_OVERVIEW = "overview"
READ_MODEL_INGEST_PIPELINE = "ingest_pipeline"
READ_MODEL_REVIEW_USAGE_PROFILE = "review_usage_profile"


class ReadSnapshotUnavailableError(RuntimeError):
    def __init__(self, cache_key: str, reason: str = "database_locked"):
        super().__init__(reason)
        self.cache_key = cache_key
        self.reason = reason


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_positive_int(value: Any, default: int, *, minimum: int = 1) -> int:
    return max(_coerce_int(value, default), minimum)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _execute_with_changes(
    conn: sqlite3.Connection,
    query: str,
    args: tuple[Any, ...] = (),
) -> int:
    cursor = conn.execute(query, args)
    if cursor.rowcount is not None and cursor.rowcount >= 0:
        return int(cursor.rowcount)
    row = conn.execute("SELECT changes() AS cnt").fetchone()
    return int(row["cnt"] if row else 0)


def _module_metadata_from_json(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if raw_value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _normalize_module_inbound_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_module_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _coerce_module_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_module_health_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"ok", "warn", "error"}:
        return normalized
    return "warn"


def _apply_module_metadata(payload: dict[str, Any], metadata_raw: Any) -> dict[str, Any]:
    metadata = _module_metadata_from_json(metadata_raw)
    payload["metadata"] = metadata
    payload["inbound_tags"] = _normalize_module_inbound_tags(
        metadata.get("inbound_tags")
        if "inbound_tags" in metadata
        else metadata.get("config_profiles", [])
    )
    payload["install_state"] = str(payload.get("install_state") or "online").strip() or "online"
    payload["managed"] = bool(payload.get("managed"))
    payload["health_status"] = _normalize_module_health_status(payload.get("health_status"))
    payload["error_text"] = str(payload.get("error_text") or "").strip()
    payload["last_validation_at"] = str(payload.get("last_validation_at") or "").strip()
    payload["spool_depth"] = _coerce_module_int(payload.get("spool_depth"), 0)
    payload["access_log_exists"] = _coerce_module_bool(payload.get("access_log_exists"))
    payload["token_reveal_available"] = bool(str(payload.pop("token_ciphertext", "") or "").strip())
    return payload


def _module_health_snapshot(
    details: Optional[dict[str, Any]],
    *,
    current_status: Any = "warn",
    current_error_text: Any = "",
    current_last_validation_at: Any = "",
    current_spool_depth: Any = 0,
    current_access_log_exists: Any = 0,
) -> tuple[str, str, str, int, int]:
    payload = details if isinstance(details, dict) else {}
    health_status = (
        _normalize_module_health_status(payload.get("health_status"))
        if "health_status" in payload
        else _normalize_module_health_status(current_status)
    )
    error_text = (
        str(payload.get("error_text") or "").strip()
        if "error_text" in payload
        else str(current_error_text or "").strip()
    )
    if health_status == "ok":
        error_text = ""
    last_validation_at = (
        str(payload.get("last_validation_at") or "").strip()
        if "last_validation_at" in payload
        else str(current_last_validation_at or "").strip()
    )
    spool_depth = (
        _coerce_module_int(payload.get("spool_depth"), 0)
        if "spool_depth" in payload
        else _coerce_module_int(current_spool_depth, 0)
    )
    if "access_log_exists" in payload:
        access_log_exists = 1 if _coerce_module_bool(payload.get("access_log_exists")) else 0
    else:
        access_log_exists = 1 if _coerce_module_bool(current_access_log_exists) else 0
    return health_status, error_text, last_validation_at, spool_depth, access_log_exists


def _normalize_review_identity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    raw_uuid = normalized.get("uuid")
    if normalized.get("system_id") in (None, "") and raw_uuid not in (None, ""):
        raw_uuid_text = str(raw_uuid).strip()
        if raw_uuid_text.isdigit():
            normalized["system_id"] = int(raw_uuid_text)
            normalized["uuid"] = None
    return normalized


def _resolve_review_module_name(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    module_name = str(normalized.get("module_name") or "").strip()
    module_id = str(normalized.get("module_id") or "").strip()
    if module_name or not module_id:
        return normalized
    row = conn.execute(
        "SELECT module_name FROM modules WHERE module_id = ?",
        (module_id,),
    ).fetchone()
    if row and str(row["module_name"] or "").strip():
        normalized["module_name"] = str(row["module_name"]).strip()
    return normalized


def _ensure_list_of_type(key: str, value: Any, item_type: type) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    cleaned = []
    for item in value:
        try:
            cleaned.append(item_type(item))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} contains invalid value {item!r}") from exc
    return cleaned


def _normalize_string_list(key: str, value: Any) -> list[str]:
    cleaned = _ensure_list_of_type(key, value, str)
    return [item.strip().lower() for item in cleaned if item.strip()]


def _normalize_provider_profile_item(index: int, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"provider_profiles[{index}] must be an object")
    key = str(value.get("key", "")).strip().lower()
    if not key:
        raise ValueError(f"provider_profiles[{index}].key is required")
    classification = PROVIDER_CLASSIFICATION_ALIASES.get(
        str(value.get("classification", "mixed")).strip().lower()
    )
    if not classification:
        raise ValueError(f"provider_profiles[{index}].classification is invalid")
    return {
        "key": key,
        "classification": classification,
        "aliases": _normalize_string_list(f"provider_profiles[{index}].aliases", value.get("aliases", [])),
        "mobile_markers": _normalize_string_list(
            f"provider_profiles[{index}].mobile_markers", value.get("mobile_markers", [])
        ),
        "home_markers": _normalize_string_list(
            f"provider_profiles[{index}].home_markers", value.get("home_markers", [])
        ),
        "asns": _ensure_list_of_type(f"provider_profiles[{index}].asns", value.get("asns", []), int),
    }


def _normalize_provider_profiles(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("provider_profiles must be a list")
    profiles: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for index, item in enumerate(value):
        normalized = _normalize_provider_profile_item(index, item)
        if normalized["key"] in seen_keys:
            raise ValueError(f"provider_profiles contains duplicate key {normalized['key']!r}")
        seen_keys.add(normalized["key"])
        profiles.append(normalized)
    return profiles


EDITABLE_COMPLEX_TOP_LEVEL_KEYS = {
    "provider_profiles": _normalize_provider_profiles,
}


def _validate_setting(key: str, value: Any) -> Any:
    expected = EDITABLE_SETTINGS_KEYS[key]
    if expected is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError(f"{key} must be a boolean")
    if expected is str:
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        return value.strip()
    if not isinstance(value, expected):
        raise ValueError(f"{key} has invalid type")
    return value


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_day_boundary(value: Any, *, end_of_day: bool) -> str:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid date format for {value!r}, expected YYYY-MM-DD") from exc
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed.isoformat()


def _normalize_settings_for_storage(settings: dict[str, Any]) -> dict[str, Any]:
    normalized_settings: dict[str, Any] = {}
    for key, value in settings.items():
        canonical_key = LEGACY_EDITABLE_SETTING_ALIASES.get(key, key)
        if canonical_key not in EDITABLE_SETTINGS_KEYS:
            raise ValueError(f"Unsupported editable setting: {key}")
        if key in LEGACY_EDITABLE_SETTING_ALIASES and canonical_key in settings:
            continue
        normalized_settings[canonical_key] = _validate_setting(canonical_key, value)
    return normalized_settings


def _apply_editable_settings(target: dict[str, Any], source: Any) -> None:
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        canonical_key = LEGACY_EDITABLE_SETTING_ALIASES.get(key, key)
        if canonical_key not in EDITABLE_SETTINGS_KEYS:
            continue
        if key in LEGACY_EDITABLE_SETTING_ALIASES and canonical_key in source:
            continue
        target[canonical_key] = copy.deepcopy(value)


def _normalize_settings_for_runtime(source: Any, base_settings: Any) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    _apply_editable_settings(normalized, base_settings)
    _apply_editable_settings(normalized, source)
    for key, value in DEFAULT_SETTINGS.items():
        normalized.setdefault(key, value)
    return {
        key: copy.deepcopy(normalized.get(key, DEFAULT_SETTINGS.get(key)))
        for key in EDITABLE_SETTINGS_KEYS
    }


def validate_live_rules_patch(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Rules payload must be an object")

    normalized: dict[str, Any] = {}
    for key, item_type in EDITABLE_TOP_LEVEL_KEYS.items():
        if key in payload:
            normalized[key] = _ensure_list_of_type(key, payload[key], item_type)
    for key, validator in EDITABLE_COMPLEX_TOP_LEVEL_KEYS.items():
        if key in payload:
            normalized[key] = validator(payload[key])

    if "settings" in payload:
        settings = payload["settings"]
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        normalized["settings"] = _normalize_settings_for_storage(settings)

    unsupported = set(payload) - set(EDITABLE_TOP_LEVEL_KEYS) - set(EDITABLE_COMPLEX_TOP_LEVEL_KEYS) - {"settings"}
    if unsupported:
        raise ValueError(f"Unsupported live rule keys: {', '.join(sorted(unsupported))}")
    return normalized


class PlatformStore:
    def __init__(
        self,
        db_path: str,
        base_config: Optional[dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        self.db_path = db_path
        self.base_config = copy.deepcopy(base_config or {})
        self.config_path = config_path
        self._rules_cache: Optional[dict[str, Any]] = None
        self._rules_cache_meta: Optional[dict[str, Any]] = None
        self._rules_cache_mtime: Optional[float] = None
        self._mirrored_live_rules_marker: Optional[tuple[int, str, str]] = None
        self._read_cache: dict[str, tuple[float, Any]] = {}
        self.storage = SQLiteStorage(db_path)
        self.sessions = AdminSessionRepository(self.storage)
        self.admin_security = AdminSecurityRepository(self.storage)
        self.health = ServiceHealthRepository(self.storage, db_path)
        self.modules_admin = ModuleAdminRepository(self.storage)
        self.review_admin = ReviewAdminRepository(
            self.storage,
            base_config=self.base_config,
            live_rules_loader=self.get_live_rules_state,
            read_model_writer=self._write_read_model_snapshot_conn,
            read_model_loader=self._read_read_model_snapshot_conn,
        )

    def _connect(self) -> sqlite3.Connection:
        return self.storage.connect()

    def _maintenance_connect(self) -> sqlite3.Connection:
        return self.storage.connect(
            timeout=LOW_PRIORITY_SQLITE_TIMEOUT_SECONDS,
            busy_timeout_ms=LOW_PRIORITY_SQLITE_BUSY_TIMEOUT_MS,
        )

    def _fast_read_connect(self) -> sqlite3.Connection:
        return self.storage.connect(
            timeout=FAST_READ_SQLITE_TIMEOUT_SECONDS,
            busy_timeout_ms=FAST_READ_SQLITE_BUSY_TIMEOUT_MS,
            query_time_limit_ms=FAST_READ_SQLITE_QUERY_LIMIT_MS,
        )

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _write_read_model_snapshot_conn(
        self,
        conn: sqlite3.Connection,
        snapshot_type: str,
        scope_key: str,
        payload: dict[str, Any],
        updated_at: str | None = None,
    ) -> None:
        now = str(updated_at or _utcnow())
        conn.execute(
            """
            INSERT INTO read_model_snapshots (
                snapshot_type, scope_key, payload_json, updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(snapshot_type, scope_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                str(snapshot_type or "").strip(),
                str(scope_key or "").strip(),
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )

    def _read_read_model_snapshot_conn(
        self,
        conn: sqlite3.Connection,
        snapshot_type: str,
        scope_key: str,
    ) -> Optional[dict[str, Any]]:
        row = conn.execute(
            """
            SELECT payload_json, updated_at
            FROM read_model_snapshots
            WHERE snapshot_type = ? AND scope_key = ?
            """,
            (
                str(snapshot_type or "").strip(),
                str(scope_key or "").strip(),
            ),
        ).fetchone()
        if not row:
            return None
        payload = json.loads(str(row["payload_json"] or "{}"))
        if isinstance(payload, dict):
            payload.setdefault("_snapshot_updated_at", str(row["updated_at"] or ""))
            return payload
        return None

    def _ttl_cache_get(
        self,
        cache_key: str,
        ttl_seconds: float,
        loader,
        *,
        allow_stale_on_busy: bool = False,
    ) -> Any:
        now = time.monotonic()
        cached = self._read_cache.get(cache_key)
        if cached and cached[0] > now:
            return copy.deepcopy(cached[1])
        try:
            payload = loader()
        except sqlite3.OperationalError as exc:
            if allow_stale_on_busy and (is_sqlite_busy_error(exc) or is_sqlite_interrupted_error(exc)):
                reason = "query_timeout" if is_sqlite_interrupted_error(exc) else "database_locked"
                if cached:
                    logger.warning("Serving stale cache for %s because SQLite fast-read hit %s", cache_key, reason)
                    return copy.deepcopy(cached[1])
                raise ReadSnapshotUnavailableError(cache_key, reason=reason) from exc
            raise
        self._read_cache[cache_key] = (now + ttl_seconds, copy.deepcopy(payload))
        return payload

    def build_seed_rules(self) -> dict[str, Any]:
        return self._normalize_rules({})

    def _normalize_rules(self, payload: dict[str, Any]) -> dict[str, Any]:
        rules: dict[str, Any] = {}
        payload = payload if isinstance(payload, dict) else {}

        for key, item_type in EDITABLE_TOP_LEVEL_KEYS.items():
            raw_value = copy.deepcopy(payload.get(key, self.base_config.get(key, [])))
            if raw_value is None:
                raw_value = []
            rules[key] = _ensure_list_of_type(key, raw_value, item_type)
        for key, validator in EDITABLE_COMPLEX_TOP_LEVEL_KEYS.items():
            raw_value = copy.deepcopy(payload.get(key, self.base_config.get(key, [])))
            if raw_value is None:
                raw_value = []
            rules[key] = validator(raw_value)

        rules["settings"] = _normalize_settings_for_runtime(
            payload.get("settings", {}),
            self.base_config.get("settings", {}),
        )
        return rules

    def _load_rules_from_file(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.config_path and os.path.exists(self.config_path):
            current_mtime = os.path.getmtime(self.config_path)
            if (
                self._rules_cache is not None
                and self._rules_cache_meta is not None
                and self._rules_cache_mtime == current_mtime
            ):
                return copy.deepcopy(self._rules_cache), copy.deepcopy(self._rules_cache_meta)

            with open(self.config_path, "r", encoding="utf-8") as handle:
                raw_payload = json.load(handle)
            meta = dict(raw_payload.pop("_meta", {}))
            rules = self._normalize_rules(raw_payload)
            meta.setdefault("revision", 1)
            meta.setdefault("updated_at", "")
            meta.setdefault("updated_by", "system")
            if meta.get("updated_by") == "bootstrap":
                meta["updated_by"] = "system"
            self._rules_cache = copy.deepcopy(rules)
            self._rules_cache_meta = copy.deepcopy(meta)
            self._rules_cache_mtime = current_mtime
            return rules, meta

        return self.build_seed_rules(), {
            "revision": 1,
            "updated_at": "",
            "updated_by": "system",
        }

    def _write_rules_to_file(self, rules: dict[str, Any], meta: dict[str, Any]) -> None:
        if not self.config_path:
            return
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        payload = copy.deepcopy(self.base_config or {})
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as handle:
                current_payload = json.load(handle)
            current_payload.pop("_meta", None)
            if isinstance(current_payload, dict):
                payload.update(current_payload)

        settings_payload = {}
        if isinstance(payload.get("settings"), dict):
            settings_payload = copy.deepcopy(payload["settings"])
        settings_payload.pop("mobile_score_threshold", None)
        settings_payload.update(copy.deepcopy(rules.get("settings", {})))

        for key in EDITABLE_TOP_LEVEL_KEYS:
            payload[key] = list(copy.deepcopy(rules.get(key, [])))
        for key in EDITABLE_COMPLEX_TOP_LEVEL_KEYS:
            payload[key] = copy.deepcopy(rules.get(key, []))
        payload["settings"] = settings_payload
        payload = canonicalize_runtime_bound_settings(payload, os.path.dirname(self.config_path))
        payload["_meta"] = {
            "revision": int(meta.get("revision", 1)),
            "updated_at": meta.get("updated_at", ""),
            "updated_by": "system" if meta.get("updated_by") == "bootstrap" else meta.get("updated_by", "system"),
        }
        tmp_path = f"{self.config_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.config_path)
        self._rules_cache = copy.deepcopy(rules)
        self._rules_cache_meta = copy.deepcopy(meta)
        self._rules_cache_mtime = os.path.getmtime(self.config_path)

    def _mirror_live_rules_state(self, rules: dict[str, Any], meta: dict[str, Any]) -> None:
        marker = (
            int(meta.get("revision", 1)),
            str(meta.get("updated_at", "")),
            "system" if meta.get("updated_by") == "bootstrap" else str(meta.get("updated_by", "system")),
        )
        if self._mirrored_live_rules_marker == marker:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO live_rules (id, rules_json, revision, updated_at, updated_by)
                    VALUES (1, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        rules_json = excluded.rules_json,
                        revision = excluded.revision,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        json.dumps(rules, ensure_ascii=False),
                        marker[0],
                        marker[1],
                        marker[2],
                    ),
                )
                conn.commit()
            self._mirrored_live_rules_marker = marker
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                # This mirror is auxiliary: serving config from file is the source of truth.
                # Skip repeated retries for the same revision to avoid lock storms on read paths.
                self._mirrored_live_rules_marker = marker
                logger.warning("Skipping live_rules mirror update because SQLite is locked")
                return
            raise

    def init_schema(self) -> None:
        seed_rules = self.build_seed_rules()
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS modules (
                    module_id TEXT PRIMARY KEY,
                    module_name TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    token_ciphertext TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'online',
                    version TEXT,
                    protocol_version TEXT NOT NULL DEFAULT 'v1',
                    config_revision_applied INTEGER NOT NULL DEFAULT 0,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    install_state TEXT NOT NULL DEFAULT 'online',
                    managed INTEGER NOT NULL DEFAULT 0,
                    health_status TEXT NOT NULL DEFAULT 'warn',
                    error_text TEXT NOT NULL DEFAULT '',
                    last_validation_at TEXT NOT NULL DEFAULT '',
                    spool_depth INTEGER NOT NULL DEFAULT 0,
                    access_log_exists INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS module_heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version TEXT,
                    protocol_version TEXT NOT NULL DEFAULT 'v1',
                    config_revision_applied INTEGER NOT NULL DEFAULT 0,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingested_raw_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_uid TEXT NOT NULL UNIQUE,
                    module_id TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    received_at TEXT NOT NULL DEFAULT '',
                    occurred_at TEXT NOT NULL,
                    log_offset INTEGER,
                    subject_uuid TEXT,
                    username TEXT,
                    system_id INTEGER,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    raw_payload_json TEXT NOT NULL,
                    processing_state TEXT NOT NULL DEFAULT 'queued',
                    processing_owner TEXT NOT NULL DEFAULT '',
                    processing_started_at TEXT NOT NULL DEFAULT '',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    last_error_at TEXT NOT NULL DEFAULT '',
                    processed_at TEXT,
                    analysis_event_id INTEGER,
                    review_case_id INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    module_id TEXT,
                    module_name TEXT,
                    source_event_uid TEXT,
                    case_scope_key TEXT NOT NULL DEFAULT '',
                    device_scope_key TEXT NOT NULL DEFAULT '',
                    scope_type TEXT NOT NULL DEFAULT 'ip_only',
                    subject_key TEXT NOT NULL DEFAULT '',
                    uuid TEXT,
                    username TEXT,
                    system_id INTEGER,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    verdict TEXT NOT NULL,
                    confidence_band TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    isp TEXT,
                    asn INTEGER,
                    country TEXT,
                    region TEXT,
                    city TEXT,
                    loc TEXT,
                    latitude REAL,
                    longitude REAL,
                    client_device_id TEXT,
                    client_device_label TEXT,
                    client_os_family TEXT,
                    client_os_version TEXT,
                    client_app_name TEXT,
                    client_app_version TEXT,
                    punitive_eligible INTEGER NOT NULL DEFAULT 0,
                    reasons_json TEXT NOT NULL,
                    signal_flags_json TEXT NOT NULL,
                    bundle_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    review_reason TEXT NOT NULL,
                    case_scope_key TEXT NOT NULL DEFAULT '',
                    device_scope_key TEXT NOT NULL DEFAULT '',
                    scope_type TEXT NOT NULL DEFAULT 'ip_only',
                    subject_key TEXT NOT NULL DEFAULT '',
                    module_id TEXT,
                    module_name TEXT,
                    client_device_id TEXT,
                    client_device_label TEXT,
                    client_os_family TEXT,
                    client_app_name TEXT,
                    uuid TEXT,
                    username TEXT,
                    system_id INTEGER,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    verdict TEXT NOT NULL,
                    confidence_band TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    isp TEXT,
                    asn INTEGER,
                    provider_key TEXT,
                    provider_classification TEXT NOT NULL DEFAULT 'unknown',
                    provider_service_hint TEXT NOT NULL DEFAULT 'unknown',
                    provider_conflict INTEGER NOT NULL DEFAULT 0,
                    provider_review_recommended INTEGER NOT NULL DEFAULT 0,
                    punitive_eligible INTEGER NOT NULL DEFAULT 0,
                    latest_event_id INTEGER NOT NULL,
                    repeat_count INTEGER NOT NULL DEFAULT 1,
                    last_repeat_at TEXT NOT NULL DEFAULT '',
                    reason_codes_json TEXT NOT NULL,
                    usage_profile_summary TEXT NOT NULL DEFAULT '',
                    usage_profile_signal_count INTEGER NOT NULL DEFAULT 0,
                    usage_profile_priority INTEGER NOT NULL DEFAULT 0,
                    usage_profile_soft_reasons_json TEXT NOT NULL DEFAULT '[]',
                    usage_profile_ongoing_duration_seconds INTEGER,
                    usage_profile_ongoing_duration_text TEXT NOT NULL DEFAULT '',
                    opened_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_case_ips (
                    case_id INTEGER NOT NULL,
                    ip TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    isp TEXT,
                    asn INTEGER,
                    PRIMARY KEY (case_id, ip)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_case_modules (
                    case_id INTEGER NOT NULL,
                    module_id TEXT NOT NULL DEFAULT '',
                    module_name TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY (case_id, module_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_resolutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    event_id INTEGER,
                    resolution TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    actor_tg_id INTEGER,
                    note TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(case_id, pattern_type, pattern_value, decision)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unsure_learning (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    UNIQUE(pattern_type, pattern_value, decision)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exact_ip_overrides (
                    ip TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    source TEXT NOT NULL,
                    actor TEXT,
                    actor_tg_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_patterns_active (
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    support INTEGER NOT NULL,
                    precision REAL NOT NULL,
                    promoted_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(pattern_type, pattern_value)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_pattern_stats (
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    support INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    precision REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(pattern_type, pattern_value, decision)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_rules (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    rules_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_rule_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT NOT NULL,
                    actor_tg_id INTEGER,
                    created_at TEXT NOT NULL,
                    changes_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_identities (
                    subject TEXT PRIMARY KEY,
                    auth_method TEXT NOT NULL,
                    role TEXT NOT NULL,
                    telegram_id INTEGER,
                    username TEXT,
                    first_name TEXT,
                    totp_secret_cipher TEXT NOT NULL DEFAULT '',
                    totp_enabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_totp_challenges (
                    token TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    auth_method TEXT NOT NULL,
                    role TEXT NOT NULL,
                    telegram_id INTEGER,
                    username TEXT,
                    first_name TEXT,
                    challenge_kind TEXT NOT NULL,
                    temp_secret_cipher TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_action_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_subject TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    actor_auth_method TEXT NOT NULL,
                    actor_telegram_id INTEGER,
                    actor_username TEXT,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS service_heartbeats (
                    service_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS enforcement_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_key TEXT NOT NULL UNIQUE,
                    event_uid TEXT NOT NULL,
                    analysis_event_id INTEGER,
                    review_case_id INTEGER,
                    module_id TEXT,
                    subject_uuid TEXT,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    processing_owner TEXT NOT NULL DEFAULT '',
                    processing_started_at TEXT NOT NULL DEFAULT '',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    last_error_at TEXT NOT NULL DEFAULT '',
                    applied_at TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS read_model_snapshots (
                    snapshot_type TEXT NOT NULL,
                    scope_key TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (snapshot_type, scope_key)
                )
                """
            )

            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(ip_decisions)").fetchall()
            }
            if columns and "bundle_json" not in columns:
                conn.execute("ALTER TABLE ip_decisions ADD COLUMN bundle_json TEXT")
            raw_event_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(ingested_raw_events)").fetchall()
            }
            if raw_event_columns and "received_at" not in raw_event_columns:
                conn.execute("ALTER TABLE ingested_raw_events ADD COLUMN received_at TEXT NOT NULL DEFAULT ''")
            if raw_event_columns and "processing_state" not in raw_event_columns:
                conn.execute(
                    "ALTER TABLE ingested_raw_events ADD COLUMN processing_state TEXT NOT NULL DEFAULT 'queued'"
                )
            if raw_event_columns and "processing_owner" not in raw_event_columns:
                conn.execute(
                    "ALTER TABLE ingested_raw_events ADD COLUMN processing_owner TEXT NOT NULL DEFAULT ''"
                )
            if raw_event_columns and "processing_started_at" not in raw_event_columns:
                conn.execute(
                    "ALTER TABLE ingested_raw_events ADD COLUMN processing_started_at TEXT NOT NULL DEFAULT ''"
                )
            if raw_event_columns and "attempt_count" not in raw_event_columns:
                conn.execute(
                    "ALTER TABLE ingested_raw_events ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
                )
            if raw_event_columns and "next_attempt_at" not in raw_event_columns:
                conn.execute(
                    "ALTER TABLE ingested_raw_events ADD COLUMN next_attempt_at TEXT NOT NULL DEFAULT ''"
                )
            if raw_event_columns and "last_error" not in raw_event_columns:
                conn.execute(
                    "ALTER TABLE ingested_raw_events ADD COLUMN last_error TEXT NOT NULL DEFAULT ''"
                )
            if raw_event_columns and "last_error_at" not in raw_event_columns:
                conn.execute(
                    "ALTER TABLE ingested_raw_events ADD COLUMN last_error_at TEXT NOT NULL DEFAULT ''"
                )
            analysis_event_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(analysis_events)").fetchall()
            }
            if analysis_event_columns and "module_id" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN module_id TEXT")
            if analysis_event_columns and "module_name" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN module_name TEXT")
            if analysis_event_columns and "source_event_uid" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN source_event_uid TEXT")
            if analysis_event_columns and "case_scope_key" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN case_scope_key TEXT NOT NULL DEFAULT ''")
            if analysis_event_columns and "device_scope_key" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN device_scope_key TEXT NOT NULL DEFAULT ''")
            if analysis_event_columns and "scope_type" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'ip_only'")
            if analysis_event_columns and "subject_key" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN subject_key TEXT NOT NULL DEFAULT ''")
            if analysis_event_columns and "system_id" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN system_id INTEGER")
            if analysis_event_columns and "score" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN score INTEGER NOT NULL DEFAULT 0")
            if analysis_event_columns and "isp" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN isp TEXT")
            if analysis_event_columns and "asn" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN asn INTEGER")
            if analysis_event_columns and "country" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN country TEXT")
            if analysis_event_columns and "region" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN region TEXT")
            if analysis_event_columns and "city" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN city TEXT")
            if analysis_event_columns and "loc" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN loc TEXT")
            if analysis_event_columns and "latitude" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN latitude REAL")
            if analysis_event_columns and "longitude" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN longitude REAL")
            if analysis_event_columns and "client_device_id" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN client_device_id TEXT")
            if analysis_event_columns and "client_device_label" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN client_device_label TEXT")
            if analysis_event_columns and "client_os_family" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN client_os_family TEXT")
            if analysis_event_columns and "client_os_version" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN client_os_version TEXT")
            if analysis_event_columns and "client_app_name" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN client_app_name TEXT")
            if analysis_event_columns and "client_app_version" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN client_app_version TEXT")
            if analysis_event_columns and "punitive_eligible" not in analysis_event_columns:
                conn.execute(
                    "ALTER TABLE analysis_events ADD COLUMN punitive_eligible INTEGER NOT NULL DEFAULT 0"
                )
            if analysis_event_columns and "reasons_json" not in analysis_event_columns:
                conn.execute(
                    "ALTER TABLE analysis_events ADD COLUMN reasons_json TEXT NOT NULL DEFAULT '[]'"
                )
            if analysis_event_columns and "signal_flags_json" not in analysis_event_columns:
                conn.execute(
                    "ALTER TABLE analysis_events ADD COLUMN signal_flags_json TEXT NOT NULL DEFAULT '{}'"
                )
            if analysis_event_columns and "bundle_json" not in analysis_event_columns:
                conn.execute(
                    "ALTER TABLE analysis_events ADD COLUMN bundle_json TEXT NOT NULL DEFAULT '{}'"
                )
            review_case_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(review_cases)").fetchall()
            }
            if review_case_columns and "module_id" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN module_id TEXT")
            if review_case_columns and "module_name" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN module_name TEXT")
            if review_case_columns and "case_scope_key" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN case_scope_key TEXT NOT NULL DEFAULT ''")
            if review_case_columns and "device_scope_key" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN device_scope_key TEXT NOT NULL DEFAULT ''")
            if review_case_columns and "scope_type" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'ip_only'")
            if review_case_columns and "subject_key" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN subject_key TEXT NOT NULL DEFAULT ''")
            if review_case_columns and "client_device_id" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN client_device_id TEXT")
            if review_case_columns and "client_device_label" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN client_device_label TEXT")
            if review_case_columns and "client_os_family" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN client_os_family TEXT")
            if review_case_columns and "client_app_name" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN client_app_name TEXT")
            if review_case_columns and "punitive_eligible" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN punitive_eligible INTEGER NOT NULL DEFAULT 0")
            if review_case_columns and "provider_key" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN provider_key TEXT")
            if review_case_columns and "provider_classification" not in review_case_columns:
                conn.execute(
                    "ALTER TABLE review_cases ADD COLUMN provider_classification TEXT NOT NULL DEFAULT 'unknown'"
                )
            if review_case_columns and "provider_service_hint" not in review_case_columns:
                conn.execute(
                    "ALTER TABLE review_cases ADD COLUMN provider_service_hint TEXT NOT NULL DEFAULT 'unknown'"
                )
            if review_case_columns and "provider_conflict" not in review_case_columns:
                conn.execute(
                    "ALTER TABLE review_cases ADD COLUMN provider_conflict INTEGER NOT NULL DEFAULT 0"
                )
            if review_case_columns and "provider_review_recommended" not in review_case_columns:
                conn.execute(
                    "ALTER TABLE review_cases ADD COLUMN provider_review_recommended INTEGER NOT NULL DEFAULT 0"
                )
            if review_case_columns and "system_id" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN system_id INTEGER")
            if review_case_columns and "usage_profile_summary" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN usage_profile_summary TEXT NOT NULL DEFAULT ''")
            if review_case_columns and "usage_profile_signal_count" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN usage_profile_signal_count INTEGER NOT NULL DEFAULT 0")
            if review_case_columns and "usage_profile_priority" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN usage_profile_priority INTEGER NOT NULL DEFAULT 0")
            if review_case_columns and "usage_profile_soft_reasons_json" not in review_case_columns:
                conn.execute(
                    "ALTER TABLE review_cases ADD COLUMN usage_profile_soft_reasons_json TEXT NOT NULL DEFAULT '[]'"
                )
            if review_case_columns and "usage_profile_ongoing_duration_seconds" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN usage_profile_ongoing_duration_seconds INTEGER")
            if review_case_columns and "usage_profile_ongoing_duration_text" not in review_case_columns:
                conn.execute(
                    "ALTER TABLE review_cases ADD COLUMN usage_profile_ongoing_duration_text TEXT NOT NULL DEFAULT ''"
                )
            if review_case_columns and "last_repeat_at" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN last_repeat_at TEXT NOT NULL DEFAULT ''")
            live_rules_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(live_rules)").fetchall()
            }
            if live_rules_columns and "revision" not in live_rules_columns:
                conn.execute("ALTER TABLE live_rules ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
            module_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(modules)").fetchall()
            }
            if module_columns and "token_ciphertext" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN token_ciphertext TEXT NOT NULL DEFAULT ''")
            if module_columns and "install_state" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN install_state TEXT NOT NULL DEFAULT 'online'")
            if module_columns and "managed" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN managed INTEGER NOT NULL DEFAULT 0")
            if module_columns and "health_status" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN health_status TEXT NOT NULL DEFAULT 'warn'")
            if module_columns and "error_text" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN error_text TEXT NOT NULL DEFAULT ''")
            if module_columns and "last_validation_at" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN last_validation_at TEXT NOT NULL DEFAULT ''")
            if module_columns and "spool_depth" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN spool_depth INTEGER NOT NULL DEFAULT 0")
            if module_columns and "access_log_exists" not in module_columns:
                conn.execute("ALTER TABLE modules ADD COLUMN access_log_exists INTEGER NOT NULL DEFAULT 0")

            now = _utcnow()
            conn.execute(
                """
                INSERT OR IGNORE INTO read_model_snapshots (snapshot_type, scope_key, payload_json, updated_at)
                VALUES (?, '', ?, ?)
                """,
                (
                    READ_MODEL_OVERVIEW,
                    json.dumps(
                        {
                            "health": {},
                            "quality": {},
                            "latest_cases": {"items": [], "count": 0, "page": 1, "page_size": 6},
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO read_model_snapshots (snapshot_type, scope_key, payload_json, updated_at)
                VALUES (?, '', ?, ?)
                """,
                (
                    READ_MODEL_INGEST_PIPELINE,
                    json.dumps(
                        {
                            "queue_depth": 0,
                            "queued_count": 0,
                            "processing_count": 0,
                            "failed_count": 0,
                            "enforcement_pending_count": 0,
                            "worker_status": "idle",
                            "last_successful_drain_at": "",
                            "current_lag_seconds": 0,
                            "oldest_queued_age_seconds": 0,
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_modules_last_seen ON modules(last_seen_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_modules_install_state ON modules(install_state, last_seen_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_module_heartbeats_module_id ON module_heartbeats(module_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ingested_raw_events_module_id ON ingested_raw_events(module_id, occurred_at DESC)"
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ingested_raw_events_processing
                ON ingested_raw_events(processing_state, next_attempt_at, received_at, id)
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_status ON review_cases(status, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_subject_status ON review_cases(subject_key, status, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_scope_status ON review_cases(case_scope_key, status, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_device_scope_status ON review_cases(device_scope_key, status, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_overview_provider ON review_cases(status, provider_classification, provider_key, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_priority ON review_cases(status, usage_profile_priority DESC, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_opened_at ON review_cases(opened_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_module_id ON review_cases(module_id, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_uuid_updated ON review_cases(uuid, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_username_updated ON review_cases(username, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_system_id ON review_cases(system_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_telegram_id ON review_cases(telegram_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_latest_event_id ON review_cases(latest_event_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_system_id ON analysis_events(system_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_created_at ON analysis_events(created_at DESC)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_events_source_event_uid ON analysis_events(source_event_uid)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_subject_created ON analysis_events(subject_key, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_scope_created ON analysis_events(case_scope_key, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_device_scope_created ON analysis_events(device_scope_key, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_module_id ON analysis_events(module_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_uuid_created ON analysis_events(uuid, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_username_created ON analysis_events(username, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_telegram_id_created ON analysis_events(telegram_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_ip ON analysis_events(ip, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_case_ips_last_seen ON review_case_ips(case_id, last_seen_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_case_modules_module_id ON review_case_modules(module_id, case_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_case_modules_last_seen ON review_case_modules(case_id, last_seen_at DESC)"
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enforcement_jobs_status
                ON enforcement_jobs(status, next_attempt_at, created_at, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_enforcement_jobs_case
                ON enforcement_jobs(review_case_id, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_read_model_snapshots_updated
                ON read_model_snapshots(snapshot_type, updated_at DESC)
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_labels_pattern ON review_labels(pattern_type, pattern_value)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_labels_case_id ON review_labels(case_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_resolutions_case_id ON review_resolutions(case_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unsure_learning_pattern ON unsure_learning(pattern_type, pattern_value)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_sessions_exp ON admin_sessions(expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_totp_challenges_exp ON admin_totp_challenges(expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_action_audit_created ON admin_action_audit(created_at DESC)"
            )

            live_rules = conn.execute("SELECT rules_json FROM live_rules WHERE id = 1").fetchone()
            if not live_rules:
                seed_meta = {"revision": 1, "updated_at": _utcnow(), "updated_by": "system"}
                conn.execute(
                    """
                    INSERT INTO live_rules (id, rules_json, revision, updated_at, updated_by)
                    VALUES (1, ?, 1, ?, ?)
                    """,
                    (json.dumps(seed_rules, ensure_ascii=False), seed_meta["updated_at"], seed_meta["updated_by"]),
                )
                self._mirrored_live_rules_marker = (
                    int(seed_meta["revision"]),
                    str(seed_meta["updated_at"]),
                    str(seed_meta["updated_by"]),
                )
            conn.commit()

    def get_module(self, module_id: str) -> Optional[dict[str, Any]]:
        return self.modules_admin.get_module(module_id)

    def create_managed_module(
        self,
        module_id: str,
        token: str,
        token_ciphertext: str,
        *,
        module_name: str,
        protocol_version: str = "v1",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self.modules_admin.create_managed_module(
            module_id,
            token,
            token_ciphertext,
            module_name=module_name,
            protocol_version=protocol_version,
            metadata=metadata,
        )

    def update_managed_module(
        self,
        module_id: str,
        *,
        module_name: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self.modules_admin.update_managed_module(
            module_id,
            module_name=module_name,
            metadata=metadata,
        )

    def get_module_token_ciphertext(self, module_id: str) -> str:
        return self.modules_admin.get_module_token_ciphertext(module_id)

    def register_module(
        self,
        module_id: str,
        token: str,
        *,
        module_name: str = "",
        version: str = "",
        protocol_version: str = "v1",
        metadata: Optional[dict[str, Any]] = None,
        config_revision_applied: int = 0,
        auto_create: bool = True,
    ) -> dict[str, Any]:
        return self.modules_admin.register_module(
            module_id,
            token,
            module_name=module_name,
            version=version,
            protocol_version=protocol_version,
            metadata=metadata,
            config_revision_applied=config_revision_applied,
            auto_create=auto_create,
        )

    def authenticate_module(self, module_id: str, token: str) -> dict[str, Any]:
        return self.modules_admin.authenticate_module(module_id, token)

    def record_module_heartbeat(
        self,
        module_id: str,
        *,
        status: str = "online",
        version: str = "",
        protocol_version: str = "v1",
        config_revision_applied: int = 0,
        details: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self.modules_admin.record_module_heartbeat(
            module_id,
            status=status,
            version=version,
            protocol_version=protocol_version,
            config_revision_applied=config_revision_applied,
            details=details,
        )

    def list_modules(
        self,
        stale_after_seconds: int = 180,
        *,
        include_counters: bool = True,
        fast_read: bool = False,
    ) -> list[dict[str, Any]]:
        return self._ttl_cache_get(
            f"modules:{int(stale_after_seconds)}:{int(include_counters)}",
            10.0,
            lambda: self.modules_admin.list_modules(
                stale_after_seconds=stale_after_seconds,
                include_counters=include_counters,
                timeout=FAST_READ_SQLITE_TIMEOUT_SECONDS if fast_read else None,
                busy_timeout_ms=FAST_READ_SQLITE_BUSY_TIMEOUT_MS if fast_read else None,
            ),
            allow_stale_on_busy=fast_read,
        )

    def ingest_raw_event(
        self,
        module_id: str,
        module_name: str,
        event_uid: str,
        occurred_at: str,
        payload: dict[str, Any],
    ) -> bool:
        return self.modules_admin.ingest_raw_event(module_id, module_name, event_uid, occurred_at, payload)

    def enqueue_raw_events(
        self,
        module_id: str,
        module_name: str,
        items: list[dict[str, Any]],
    ) -> dict[str, int]:
        accepted = 0
        duplicates = 0
        now = _utcnow()
        with self._connect() as conn:
            for item in items:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO ingested_raw_events (
                        event_uid, module_id, module_name, received_at, occurred_at, log_offset,
                        subject_uuid, username, system_id, telegram_id, ip, tag, raw_payload_json,
                        processing_state, processing_owner, processing_started_at, attempt_count,
                        next_attempt_at, last_error, last_error_at, processed_at, analysis_event_id, review_case_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', '', '', 0, ?, '', '', NULL, NULL, NULL)
                    """,
                    (
                        str(item.get("event_uid") or "").strip(),
                        module_id,
                        module_name,
                        now,
                        str(item.get("occurred_at") or "").strip(),
                        item.get("log_offset"),
                        item.get("uuid"),
                        item.get("username"),
                        item.get("system_id"),
                        item.get("telegram_id"),
                        item.get("ip"),
                        item.get("tag"),
                        json.dumps(item, ensure_ascii=False),
                        now,
                    ),
                )
                inserted = int(cursor.rowcount or 0) > 0
                if not inserted:
                    changes_row = conn.execute("SELECT changes() AS cnt").fetchone()
                    inserted = bool(changes_row and int(changes_row["cnt"] or 0) > 0)
                if inserted:
                    accepted += 1
                else:
                    duplicates += 1
            conn.commit()
        self.refresh_ingest_pipeline_snapshot()
        return {
            "accepted": accepted,
            "duplicates": duplicates,
            "queued": accepted,
        }

    def claim_raw_events(
        self,
        owner: str,
        *,
        limit: int = 25,
        claim_timeout_seconds: int = 120,
    ) -> list[dict[str, Any]]:
        now = _utcnow()
        reclaim_before = (
            datetime.utcnow().replace(microsecond=0) - timedelta(seconds=max(int(claim_timeout_seconds), 1))
        ).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingested_raw_events
                SET processing_state = 'queued',
                    processing_owner = '',
                    processing_started_at = ''
                WHERE processing_state = 'processing'
                  AND processing_started_at != ''
                  AND processing_started_at < ?
                """,
                (reclaim_before,),
            )
            rows = conn.execute(
                """
                SELECT *
                FROM ingested_raw_events
                WHERE processing_state = 'queued'
                  AND (next_attempt_at = '' OR next_attempt_at <= ?)
                ORDER BY received_at ASC, id ASC
                LIMIT ?
                """,
                (now, max(int(limit), 1)),
            ).fetchall()
            row_ids = [int(row["id"]) for row in rows]
            if row_ids:
                placeholders = ", ".join("?" for _ in row_ids)
                conn.execute(
                    f"""
                    UPDATE ingested_raw_events
                    SET processing_state = 'processing',
                        processing_owner = ?,
                        processing_started_at = ?,
                        attempt_count = attempt_count + 1
                    WHERE id IN ({placeholders})
                    """,
                    (owner, now, *row_ids),
                )
                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM ingested_raw_events
                    WHERE id IN ({placeholders})
                    ORDER BY received_at ASC, id ASC
                    """,
                    tuple(row_ids),
                ).fetchall()
            conn.commit()
        return [dict(row) for row in rows]

    def mark_raw_event_processed(
        self,
        event_uid: str,
        *,
        analysis_event_id: Optional[int] = None,
        review_case_id: Optional[int] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingested_raw_events
                SET processing_state = 'processed',
                    processing_owner = '',
                    processing_started_at = '',
                    processed_at = ?,
                    analysis_event_id = ?,
                    review_case_id = ?
                WHERE event_uid = ?
                """,
                (_utcnow(), analysis_event_id, review_case_id, event_uid),
            )
            conn.commit()
        self.refresh_ingest_pipeline_snapshot()

    def mark_raw_event_retry(
        self,
        event_uid: str,
        *,
        next_attempt_at: str,
        error_text: str,
        dead_letter: bool = False,
    ) -> None:
        next_state = "failed" if dead_letter else "queued"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ingested_raw_events
                SET processing_state = ?,
                    processing_owner = '',
                    processing_started_at = '',
                    next_attempt_at = ?,
                    last_error = ?,
                    last_error_at = ?
                WHERE event_uid = ?
                """,
                (
                    next_state,
                    str(next_attempt_at or _utcnow()),
                    str(error_text or "").strip(),
                    _utcnow(),
                    event_uid,
                ),
            )
            conn.commit()
        self.refresh_ingest_pipeline_snapshot()

    def create_enforcement_job(
        self,
        *,
        job_key: str,
        event_uid: str,
        analysis_event_id: int | None,
        review_case_id: int | None,
        module_id: str | None,
        subject_uuid: str | None,
        job_type: str,
        payload: dict[str, Any],
        status: str = "pending",
    ) -> dict[str, Any]:
        now = _utcnow()
        applied_at = now if status == "applied" else ""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enforcement_jobs (
                    job_key, event_uid, analysis_event_id, review_case_id, module_id, subject_uuid,
                    job_type, status, processing_owner, processing_started_at, attempt_count,
                    next_attempt_at, last_error, last_error_at, applied_at, payload_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', '', 0, ?, '', '', ?, ?, ?, ?)
                ON CONFLICT(job_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    str(job_key or "").strip(),
                    str(event_uid or "").strip(),
                    analysis_event_id,
                    review_case_id,
                    clean_text(module_id) or None,
                    clean_text(subject_uuid) or None,
                    str(job_type or "").strip(),
                    str(status or "pending").strip() or "pending",
                    now,
                    applied_at,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM enforcement_jobs WHERE job_key = ?",
                (str(job_key or "").strip(),),
            ).fetchone()
            conn.commit()
        self.refresh_ingest_pipeline_snapshot()
        return dict(row) if row else {}

    def claim_enforcement_jobs(
        self,
        owner: str,
        *,
        limit: int = 25,
        claim_timeout_seconds: int = 120,
    ) -> list[dict[str, Any]]:
        now = _utcnow()
        reclaim_before = (
            datetime.utcnow().replace(microsecond=0) - timedelta(seconds=max(int(claim_timeout_seconds), 1))
        ).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE enforcement_jobs
                SET processing_owner = '',
                    processing_started_at = ''
                WHERE status = 'pending'
                  AND processing_started_at != ''
                  AND processing_started_at < ?
                """,
                (reclaim_before,),
            )
            rows = conn.execute(
                """
                SELECT *
                FROM enforcement_jobs
                WHERE status = 'pending'
                  AND processing_started_at = ''
                  AND (next_attempt_at = '' OR next_attempt_at <= ?)
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (now, max(int(limit), 1)),
            ).fetchall()
            row_ids = [int(row["id"]) for row in rows]
            if row_ids:
                placeholders = ", ".join("?" for _ in row_ids)
                conn.execute(
                    f"""
                    UPDATE enforcement_jobs
                    SET processing_owner = ?,
                        processing_started_at = ?,
                        attempt_count = attempt_count + 1
                    WHERE id IN ({placeholders})
                    """,
                    (owner, now, *row_ids),
                )
                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM enforcement_jobs
                    WHERE id IN ({placeholders})
                    ORDER BY created_at ASC, id ASC
                    """,
                    tuple(row_ids),
                ).fetchall()
            conn.commit()
        return [dict(row) for row in rows]

    def mark_enforcement_job_applied(self, job_id: int) -> None:
        with self._connect() as conn:
            now = _utcnow()
            conn.execute(
                """
                UPDATE enforcement_jobs
                SET status = 'applied',
                    processing_owner = '',
                    processing_started_at = '',
                    applied_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, now, int(job_id)),
            )
            conn.commit()
        self.refresh_ingest_pipeline_snapshot()

    def mark_enforcement_job_retry(
        self,
        job_id: int,
        *,
        next_attempt_at: str,
        error_text: str,
        dead_letter: bool = False,
    ) -> None:
        next_status = "failed" if dead_letter else "pending"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE enforcement_jobs
                SET status = ?,
                    processing_owner = '',
                    processing_started_at = '',
                    next_attempt_at = ?,
                    last_error = ?,
                    last_error_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    str(next_attempt_at or _utcnow()),
                    str(error_text or "").strip(),
                    _utcnow(),
                    _utcnow(),
                    int(job_id),
                ),
            )
            conn.commit()
        self.refresh_ingest_pipeline_snapshot()

    def refresh_ingest_pipeline_snapshot(self) -> dict[str, Any]:
        now_dt = datetime.utcnow().replace(microsecond=0)
        now = now_dt.isoformat()
        with self._connect() as conn:
            previous = self._read_read_model_snapshot_conn(conn, READ_MODEL_INGEST_PIPELINE, "") or {}
            queue_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN processing_state = 'queued' THEN 1 ELSE 0 END), 0) AS queued_count,
                    COALESCE(SUM(CASE WHEN processing_state = 'processing' THEN 1 ELSE 0 END), 0) AS processing_count,
                    COALESCE(SUM(CASE WHEN processing_state = 'failed' THEN 1 ELSE 0 END), 0) AS failed_count,
                    MIN(CASE WHEN processing_state = 'queued' THEN received_at END) AS oldest_queued_at,
                    MIN(CASE WHEN processing_state IN ('queued', 'processing') THEN received_at END) AS oldest_backlog_at
                FROM ingested_raw_events
                """
            ).fetchone()
            enforcement_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_count,
                    COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_count
                FROM enforcement_jobs
                """
            ).fetchone()
            worker_row = conn.execute(
                """
                SELECT status, details_json, updated_at
                FROM service_heartbeats
                WHERE service_name = 'mobguard-ingest-worker'
                """
            ).fetchone()
            queue_depth = int(queue_row["queued_count"] or 0) + int(queue_row["processing_count"] or 0)
            enforcement_pending = int(enforcement_row["pending_count"] or 0) if enforcement_row else 0
            oldest_queued_at = str(queue_row["oldest_queued_at"] or "")
            oldest_backlog_at = str(queue_row["oldest_backlog_at"] or "")

            def _age_seconds(raw_value: str) -> int:
                if not raw_value:
                    return 0
                try:
                    return max(int((now_dt - datetime.fromisoformat(raw_value)).total_seconds()), 0)
                except ValueError:
                    return 0

            last_successful_drain_at = str(previous.get("last_successful_drain_at") or "")
            if queue_depth == 0 and enforcement_pending == 0:
                last_successful_drain_at = now

            worker_details = {}
            if worker_row and str(worker_row["details_json"] or "").strip():
                try:
                    worker_details = json.loads(str(worker_row["details_json"]))
                except (TypeError, ValueError, json.JSONDecodeError):
                    worker_details = {}

            payload = {
                "queue_depth": queue_depth,
                "queued_count": int(queue_row["queued_count"] or 0),
                "processing_count": int(queue_row["processing_count"] or 0),
                "failed_count": int(queue_row["failed_count"] or 0),
                "enforcement_pending_count": enforcement_pending,
                "enforcement_failed_count": int(enforcement_row["failed_count"] or 0) if enforcement_row else 0,
                "oldest_queued_at": oldest_queued_at or None,
                "oldest_queued_age_seconds": _age_seconds(oldest_queued_at),
                "current_lag_seconds": _age_seconds(oldest_backlog_at),
                "last_successful_drain_at": last_successful_drain_at or None,
                "worker_status": str(worker_row["status"] or "idle") if worker_row else "idle",
                "worker_updated_at": str(worker_row["updated_at"] or "") if worker_row else "",
                "worker_details": worker_details,
            }
            self._write_read_model_snapshot_conn(
                conn,
                READ_MODEL_INGEST_PIPELINE,
                "",
                payload,
                now,
            )
            conn.commit()
            return payload

    def get_ingest_pipeline_status(self) -> dict[str, Any]:
        with self._connect() as conn:
            payload = self._read_read_model_snapshot_conn(conn, READ_MODEL_INGEST_PIPELINE, "")
        if payload is None:
            return self.refresh_ingest_pipeline_snapshot()
        return payload

    def get_live_rules(self) -> dict[str, Any]:
        return self.get_live_rules_state()["rules"]

    def get_live_rules_state(self, *, skip_db_mirror: bool = False) -> dict[str, Any]:
        payload, meta = self._load_rules_from_file()
        if not skip_db_mirror:
            self._mirror_live_rules_state(payload, meta)
        return {
            "rules": payload,
            "revision": int(meta["revision"]),
            "updated_at": meta["updated_at"],
            "updated_by": meta["updated_by"],
        }

    def sync_runtime_config(self, runtime_config: dict[str, Any]) -> dict[str, Any]:
        live_rules = self.get_live_rules()
        for key in EDITABLE_TOP_LEVEL_KEYS:
            if key in live_rules:
                runtime_config[key] = list(live_rules[key])
        for key in EDITABLE_COMPLEX_TOP_LEVEL_KEYS:
            if key in live_rules:
                runtime_config[key] = copy.deepcopy(live_rules[key])
        runtime_config.setdefault("settings", {})
        runtime_config["settings"].pop("mobile_score_threshold", None)
        for key in EDITABLE_SETTINGS_KEYS:
            if key in live_rules.get("settings", {}):
                runtime_config["settings"][key] = live_rules["settings"][key]
        return live_rules

    def update_live_rules(
        self,
        patch: dict[str, Any],
        actor: str,
        actor_tg_id: Optional[int] = None,
        expected_revision: Optional[int] = None,
        expected_updated_at: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized = validate_live_rules_patch(patch)
        current_state = self.get_live_rules_state()
        current = current_state["rules"]
        merged = copy.deepcopy(current)
        for key, value in normalized.items():
            if key == "settings":
                merged.setdefault("settings", {})
                merged["settings"].update(value)
            else:
                merged[key] = value

        now = _utcnow()
        current_revision = int(current_state["revision"])
        current_updated_at = current_state["updated_at"]
        if expected_revision is not None and expected_revision != current_revision:
            raise ValueError("Live rules revision conflict")
        if expected_updated_at and expected_updated_at != current_updated_at:
            raise ValueError("Live rules updated_at conflict")
        next_revision = current_revision + 1
        meta = {
            "revision": next_revision,
            "updated_at": now,
            "updated_by": actor,
        }
        self._write_rules_to_file(merged, meta)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE live_rules
                SET rules_json = ?, revision = ?, updated_at = ?, updated_by = ?
                WHERE id = 1
                """,
                (json.dumps(merged, ensure_ascii=False), next_revision, now, actor),
            )
            conn.execute(
                """
                INSERT INTO live_rule_audit (actor, actor_tg_id, created_at, changes_json)
                VALUES (?, ?, ?, ?)
                """,
                (actor, actor_tg_id, now, json.dumps(normalized, ensure_ascii=False)),
            )
            conn.commit()
        self._mirrored_live_rules_marker = (
            int(next_revision),
            str(now),
            str(actor),
        )
        return {
            "rules": merged,
            "revision": next_revision,
            "updated_at": now,
            "updated_by": actor,
        }

    def get_ip_override(self, ip: str) -> Optional[str]:
        now = _utcnow()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT decision, expires_at
                FROM exact_ip_overrides
                WHERE ip = ?
                """,
                (ip,),
            ).fetchone()
        if not row:
            return None
        expires_at = row["expires_at"]
        if expires_at and expires_at <= now:
            return None
        return row["decision"]

    def set_ip_override(
        self,
        ip: str,
        decision: str,
        source: str,
        actor: str,
        actor_tg_id: Optional[int] = None,
        ttl_days: int = 7,
    ) -> None:
        now = _utcnow()
        expires_at = (datetime.utcnow() + timedelta(days=ttl_days)).replace(microsecond=0).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO exact_ip_overrides (ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    decision = excluded.decision,
                    source = excluded.source,
                    actor = excluded.actor,
                    actor_tg_id = excluded.actor_tg_id,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (ip, decision, source, actor, actor_tg_id, now, now, expires_at),
            )
            conn.commit()

    def record_analysis_event(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        observation: Optional[dict[str, Any]] = None,
        source_event_uid: str | None = None,
    ) -> int:
        return self.review_admin.record_analysis_event(
            user,
            ip,
            tag,
            bundle,
            observation=observation,
            source_event_uid=source_event_uid,
        )

    def build_review_url(self, case_id: int) -> str:
        return self.review_admin.build_review_url(case_id)

    def ensure_review_case(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        event_id: int,
        review_reason: str,
    ) -> ReviewCaseSummary:
        return self.review_admin.ensure_review_case(user, ip, tag, bundle, event_id, review_reason)

    def recheck_review_case(
        self,
        case_id: int,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        review_reason: str | None,
        actor: str,
        actor_tg_id: Optional[int] = None,
        note: str = "",
    ) -> dict[str, Any]:
        return self.review_admin.recheck_review_case(
            case_id,
            user,
            ip,
            tag,
            bundle,
            review_reason,
            actor,
            actor_tg_id,
            note,
        )

    def _hydrate_review_list_item(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row | dict[str, Any],
    ) -> dict[str, Any]:
        return self.review_admin._hydrate_review_list_item(conn, row)

    def _decode_analysis_event_payload(self, event_row: sqlite3.Row | None) -> dict[str, Any]:
        return self.review_admin._decode_analysis_event_payload(event_row)

    def list_review_cases(self, filters: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self.review_admin.list_review_cases(filters)

    def list_review_case_teasers(
        self,
        *,
        status: str = "OPEN",
        limit: int = 6,
        fast_read: bool = False,
    ) -> list[dict[str, Any]]:
        return self.review_admin.list_review_case_teasers(
            status=status,
            limit=limit,
            timeout=FAST_READ_SQLITE_TIMEOUT_SECONDS if fast_read else None,
            busy_timeout_ms=FAST_READ_SQLITE_BUSY_TIMEOUT_MS if fast_read else None,
        )

    def get_review_case(self, case_id: int) -> dict[str, Any]:
        return self.review_admin.get_review_case(case_id)

    def _record_labels_for_resolution(
        self,
        conn: sqlite3.Connection,
        case_id: int,
        event_id: int,
        bundle: DecisionBundle,
        decision: str,
    ) -> None:
        self.review_admin._record_labels_for_resolution(conn, case_id, event_id, bundle, decision)

    def promote_learning_patterns(self) -> None:
        self.review_admin.promote_learning_patterns()

    def get_promoted_pattern(self, pattern_type: str, pattern_value: str) -> Optional[dict[str, Any]]:
        return self.review_admin.get_promoted_pattern(pattern_type, pattern_value)

    def resolve_review_case(
        self,
        case_id: int,
        resolution: str,
        actor: str,
        actor_tg_id: Optional[int] = None,
        note: str = "",
    ) -> dict[str, Any]:
        return self.review_admin.resolve_review_case(case_id, resolution, actor, actor_tg_id, note)

    def _build_quality_metrics(self, module_filter: str) -> dict[str, Any]:
        live_rules_state = self.get_live_rules_state(skip_db_mirror=True)
        runtime_dir = os.path.dirname(self.config_path) if self.config_path else os.path.dirname(self.db_path)
        asn_source = detect_asn_source(runtime_dir, self.base_config.get("settings", {}).get("geoip_db"))
        learning_thresholds = {
            "asn_min_support": int(
                live_rules_state["rules"].get("settings", {}).get("learning_promote_asn_min_support", 10)
            ),
            "asn_min_precision": float(
                live_rules_state["rules"].get("settings", {}).get("learning_promote_asn_min_precision", 0.95)
            ),
            "combo_min_support": int(
                live_rules_state["rules"].get("settings", {}).get("learning_promote_combo_min_support", 5)
            ),
            "combo_min_precision": float(
                live_rules_state["rules"].get("settings", {}).get("learning_promote_combo_min_precision", 0.90)
            ),
        }
        if module_filter:
            review_case_where = (
                "WHERE EXISTS (SELECT 1 FROM review_case_modules rcm WHERE rcm.case_id = review_cases.id AND rcm.module_id = ?)"
            )
            review_case_params: tuple[Any, ...] = (module_filter,)
            open_case_where = (
                "WHERE status = 'OPEN' AND EXISTS (SELECT 1 FROM review_case_modules rcm WHERE rcm.case_id = review_cases.id AND rcm.module_id = ?)"
            )
            open_case_params: tuple[Any, ...] = (module_filter,)
            resolution_join = (
                """
                FROM review_resolutions rr
                JOIN review_cases rc ON rc.id = rr.case_id
                WHERE EXISTS (
                    SELECT 1
                    FROM review_case_modules rcm
                    WHERE rcm.case_id = rc.id AND rcm.module_id = ?
                )
                """
            )
            resolution_params: tuple[Any, ...] = (module_filter,)
            provider_where = (
                """
                WHERE rc.status = 'OPEN'
                  AND rc.provider_classification = 'mixed'
                  AND EXISTS (
                      SELECT 1
                      FROM review_case_modules rcm
                      WHERE rcm.case_id = rc.id AND rcm.module_id = ?
                  )
                """
            )
            provider_params: tuple[Any, ...] = (module_filter,)
        else:
            review_case_where = ""
            review_case_params = ()
            open_case_where = "WHERE status = 'OPEN'"
            open_case_params = ()
            resolution_join = "FROM review_resolutions"
            resolution_params = ()
            provider_where = "WHERE rc.status = 'OPEN' AND rc.provider_classification = 'mixed'"
            provider_params = ()

        with self._connect() as conn:
            open_cases = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM review_cases {open_case_where}",
                open_case_params,
            ).fetchone()["cnt"]
            total_cases = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM review_cases {review_case_where}",
                review_case_params,
            ).fetchone()["cnt"]
            resolved_home = conn.execute(
                f"SELECT COUNT(*) AS cnt {resolution_join} AND resolution = 'HOME'" if module_filter else "SELECT COUNT(*) AS cnt FROM review_resolutions WHERE resolution = 'HOME'",
                resolution_params if module_filter else (),
            ).fetchone()["cnt"]
            resolved_mobile = conn.execute(
                f"SELECT COUNT(*) AS cnt {resolution_join} AND resolution = 'MOBILE'" if module_filter else "SELECT COUNT(*) AS cnt FROM review_resolutions WHERE resolution = 'MOBILE'",
                resolution_params if module_filter else (),
            ).fetchone()["cnt"]
            skipped = conn.execute(
                f"SELECT COUNT(*) AS cnt {resolution_join} AND resolution = 'SKIP'" if module_filter else "SELECT COUNT(*) AS cnt FROM review_resolutions WHERE resolution = 'SKIP'",
                resolution_params if module_filter else (),
            ).fetchone()["cnt"]
            top_noisy = conn.execute(
                """
                SELECT COALESCE(CAST(asn AS TEXT), 'unknown') AS asn_key, COUNT(*) AS cnt
                FROM review_cases
                {where_sql}
                GROUP BY asn_key
                ORDER BY cnt DESC
                LIMIT 10
                """.format(where_sql=review_case_where),
                review_case_params,
            ).fetchall()
            active_patterns = conn.execute(
                "SELECT COUNT(*) AS cnt FROM learning_patterns_active"
            ).fetchone()["cnt"]
            top_patterns = conn.execute(
                """
                SELECT pattern_type, pattern_value, decision, support, precision
                FROM learning_patterns_active
                ORDER BY support DESC, precision DESC
                LIMIT 10
                """
            ).fetchall()
            promoted_by_type = conn.execute(
                """
                SELECT pattern_type, COUNT(*) AS count, COALESCE(SUM(support), 0) AS total_support,
                       COALESCE(AVG(precision), 0) AS avg_precision
                FROM learning_patterns_active
                GROUP BY pattern_type
                ORDER BY total_support DESC, count DESC
                """
            ).fetchall()
            legacy_total_patterns = 0
            legacy_total_confidence = 0
            legacy_by_type: list[sqlite3.Row] = []
            legacy_top_patterns: list[sqlite3.Row] = []
            if self._table_exists(conn, "unsure_learning"):
                legacy_totals = conn.execute(
                    "SELECT COUNT(*) AS count, COALESCE(SUM(confidence), 0) AS total_confidence FROM unsure_learning"
                ).fetchone()
                legacy_total_patterns = int(legacy_totals["count"] or 0)
                legacy_total_confidence = int(legacy_totals["total_confidence"] or 0)
                legacy_by_type = conn.execute(
                    """
                    SELECT pattern_type, COUNT(*) AS count, COALESCE(SUM(confidence), 0) AS total_confidence
                    FROM unsure_learning
                    GROUP BY pattern_type
                    ORDER BY total_confidence DESC, count DESC
                    """
                ).fetchall()
                legacy_top_patterns = conn.execute(
                    """
                    SELECT pattern_type, pattern_value, decision, confidence, timestamp
                    FROM unsure_learning
                    ORDER BY confidence DESC, timestamp DESC
                    LIMIT 10
                    """
                ).fetchall()
            active_sessions = conn.execute(
                "SELECT COUNT(*) AS cnt FROM admin_sessions WHERE expires_at > ?",
                (_utcnow(),),
            ).fetchone()["cnt"]
            provider_rows = conn.execute(
                f"""
                SELECT rc.provider_key, rc.provider_conflict, rc.review_reason, rc.verdict
                FROM review_cases rc
                {provider_where}
                """,
                provider_params,
            ).fetchall()
            module_rows = conn.execute(
                """
                SELECT module_id, module_name, status, version, protocol_version, config_revision_applied, last_seen_at
                FROM modules
                ORDER BY last_seen_at DESC, module_id ASC
                """
            ).fetchall()
        mixed_provider_open_cases = 0
        mixed_provider_conflict_cases = 0
        mixed_provider_stats: dict[str, dict[str, Any]] = {}
        for row in provider_rows:
            provider_key = str(row["provider_key"] or "").strip().lower()
            if not provider_key:
                continue
            mixed_provider_open_cases += 1
            conflict_case = bool(row["provider_conflict"]) or str(row["review_reason"]) == "provider_conflict"
            if conflict_case:
                mixed_provider_conflict_cases += 1
            bucket = mixed_provider_stats.setdefault(
                provider_key,
                {
                    "provider_key": provider_key,
                    "open_cases": 0,
                    "conflict_cases": 0,
                    "home_cases": 0,
                    "mobile_cases": 0,
                    "unsure_cases": 0,
                },
            )
            bucket["open_cases"] += 1
            if conflict_case:
                bucket["conflict_cases"] += 1
            verdict = str(row["verdict"] or "").upper()
            if verdict == "HOME":
                bucket["home_cases"] += 1
            elif verdict == "MOBILE":
                bucket["mobile_cases"] += 1
            else:
                bucket["unsure_cases"] += 1
        top_mixed_providers = sorted(
            mixed_provider_stats.values(),
            key=lambda item: (-int(item["open_cases"]), -int(item["conflict_cases"]), item["provider_key"]),
        )[:10]
        return {
            "open_cases": open_cases,
            "total_cases": total_cases,
            "resolved_home": resolved_home,
            "resolved_mobile": resolved_mobile,
            "skipped": skipped,
            "resolution_total": resolved_home + resolved_mobile + skipped,
            "active_learning_patterns": active_patterns,
            "top_noisy_asns": [dict(row) for row in top_noisy],
            "top_patterns": [dict(row) for row in top_patterns],
            "live_rules_revision": int(live_rules_state["revision"] or 1),
            "live_rules_updated_at": live_rules_state["updated_at"],
            "live_rules_updated_by": live_rules_state["updated_by"],
            "active_sessions": active_sessions,
            "selected_module_id": module_filter or None,
            "asn_source": asn_source,
            "modules": [dict(row) for row in module_rows],
            "mixed_providers": {
                "open_cases": mixed_provider_open_cases,
                "conflict_cases": mixed_provider_conflict_cases,
                "conflict_rate": (
                    mixed_provider_conflict_cases / mixed_provider_open_cases
                    if mixed_provider_open_cases
                    else 0.0
                ),
                "top_open_cases": top_mixed_providers,
            },
            "learning": {
                "thresholds": learning_thresholds,
                "promoted": {
                    "active_patterns": active_patterns,
                    "by_type": [dict(row) for row in promoted_by_type],
                    "top_patterns": [dict(row) for row in top_patterns],
                },
                "legacy": {
                    "total_patterns": legacy_total_patterns,
                    "total_confidence": legacy_total_confidence,
                    "by_type": [dict(row) for row in legacy_by_type],
                    "top_patterns": [dict(row) for row in legacy_top_patterns],
                },
            },
        }

    def get_quality_metrics(self, module_id: str | None = None) -> dict[str, Any]:
        module_filter = str(module_id or "").strip()
        return self._ttl_cache_get(
            f"quality:{module_filter}",
            10.0,
            lambda: self._build_quality_metrics(module_filter),
        )

    def _build_overview_metrics(self, *, fast_read: bool = False) -> dict[str, Any]:
        quality = self._build_quality_metrics("")
        latest_cases = self.review_admin.list_review_cases(
            {
                "status": "OPEN",
                "page": 1,
                "page_size": 6,
                "sort": "updated_desc",
            }
        )
        return {
            "health": self.get_health_snapshot(fast_read=fast_read),
            "quality": quality,
            "latest_cases": latest_cases,
        }

    def refresh_overview_snapshot(self) -> dict[str, Any]:
        payload = self._build_overview_metrics(fast_read=False)
        with self._connect() as conn:
            self._write_read_model_snapshot_conn(
                conn,
                READ_MODEL_OVERVIEW,
                "",
                payload,
                _utcnow(),
            )
            conn.commit()
        self._read_cache.pop("overview", None)
        return payload

    def get_overview_metrics(self) -> dict[str, Any]:
        with self._connect() as conn:
            payload = self._read_read_model_snapshot_conn(conn, READ_MODEL_OVERVIEW, "")
            snapshot_updated_at = str((payload or {}).get("_snapshot_updated_at") or "")
        if payload is None or not isinstance(payload.get("quality"), dict) or not payload.get("quality"):
            try:
                payload = self.refresh_overview_snapshot()
                snapshot_updated_at = _utcnow()
            except sqlite3.OperationalError:
                if payload is None:
                    raise

        pipeline = self.get_ingest_pipeline_status()

        def _age_seconds(raw_value: str) -> int:
            if not raw_value:
                return 0
            try:
                return max(
                    int((datetime.utcnow().replace(microsecond=0) - datetime.fromisoformat(raw_value)).total_seconds()),
                    0,
                )
            except ValueError:
                return 0

        response = copy.deepcopy(payload)
        response["pipeline"] = pipeline
        response["freshness"] = {
            "overview_updated_at": snapshot_updated_at or None,
            "overview_age_seconds": _age_seconds(snapshot_updated_at),
            "pipeline_updated_at": pipeline.get("_snapshot_updated_at") or None,
            "pipeline_age_seconds": _age_seconds(str(pipeline.get("_snapshot_updated_at") or "")),
        }
        return response

    def get_db_maintenance_settings(self) -> dict[str, int]:
        settings = self.get_live_rules_state(skip_db_mirror=True)["rules"].get("settings", {})
        subnet_mobile_ttl = _coerce_positive_int(
            settings.get("subnet_mobile_ttl_days"),
            int(DEFAULT_SETTINGS.get("subnet_mobile_ttl_days", 45)),
        )
        subnet_home_ttl = _coerce_positive_int(
            settings.get("subnet_home_ttl_days"),
            int(DEFAULT_SETTINGS.get("subnet_home_ttl_days", 21)),
        )
        resolved_review_retention_days = _coerce_positive_int(
            settings.get("resolved_review_retention_days"),
            int(DEFAULT_SETTINGS["resolved_review_retention_days"]),
        )
        return {
            "db_cleanup_interval_minutes": _coerce_positive_int(
                settings.get("db_cleanup_interval_minutes"),
                int(DEFAULT_SETTINGS["db_cleanup_interval_minutes"]),
            ),
            "module_heartbeats_retention_days": _coerce_positive_int(
                settings.get("module_heartbeats_retention_days"),
                int(DEFAULT_SETTINGS["module_heartbeats_retention_days"]),
            ),
            "ingested_raw_events_retention_days": _coerce_positive_int(
                settings.get("ingested_raw_events_retention_days"),
                int(DEFAULT_SETTINGS["ingested_raw_events_retention_days"]),
            ),
            "ip_history_retention_days": _coerce_positive_int(
                settings.get("ip_history_retention_days"),
                int(DEFAULT_SETTINGS["ip_history_retention_days"]),
            ),
            "orphan_analysis_events_retention_days": _coerce_positive_int(
                settings.get("orphan_analysis_events_retention_days"),
                int(DEFAULT_SETTINGS["orphan_analysis_events_retention_days"]),
            ),
            "resolved_review_retention_days": resolved_review_retention_days,
            "violation_history_retention_days": resolved_review_retention_days,
            "subnet_evidence_retention_days": max(subnet_mobile_ttl, subnet_home_ttl),
        }

    def run_db_maintenance(self, mode: str = "periodic") -> dict[str, Any]:
        normalized_mode = str(mode or "periodic").strip().lower()
        if normalized_mode not in {"periodic", "emergency"}:
            raise ValueError("Maintenance mode must be periodic or emergency")

        settings = self.get_db_maintenance_settings()
        now_utc = datetime.utcnow().replace(microsecond=0)
        trackers_cutoff = (now_utc - timedelta(hours=1)).isoformat()
        ip_decision_cutoff = now_utc.isoformat()
        unsure_patterns_cutoff = (now_utc - timedelta(days=7)).isoformat()
        daily_stats_cutoff = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")
        exact_override_cutoff = now_utc.isoformat()
        module_heartbeats_cutoff = (
            now_utc - timedelta(days=settings["module_heartbeats_retention_days"])
        ).isoformat()
        ingested_raw_events_cutoff = (
            now_utc - timedelta(days=settings["ingested_raw_events_retention_days"])
        ).isoformat()
        ip_history_cutoff = (
            now_utc - timedelta(days=settings["ip_history_retention_days"])
        ).isoformat()
        subnet_evidence_cutoff = (
            now_utc - timedelta(days=settings["subnet_evidence_retention_days"])
        ).isoformat()
        violation_history_cutoff = (
            now_utc - timedelta(days=settings["violation_history_retention_days"])
        ).isoformat()
        resolved_review_cutoff = (
            now_utc - timedelta(days=settings["resolved_review_retention_days"])
        ).isoformat()
        orphan_analysis_events_cutoff = (
            now_utc - timedelta(days=settings["orphan_analysis_events_retention_days"])
        ).isoformat()
        deleted: dict[str, int] = {}
        report = {
            "mode": normalized_mode,
            "started_at": now_utc.isoformat(),
            "deleted": deleted,
            "settings": settings,
            "wal_checkpoint": [],
            "vacuumed": False,
            "skipped": False,
            "skip_reason": None,
        }
        try:
            with self._maintenance_connect() as conn:
                if self._table_exists(conn, "active_trackers"):
                    deleted["active_trackers"] = _execute_with_changes(
                        conn,
                        "DELETE FROM active_trackers WHERE last_seen < ?",
                        (trackers_cutoff,),
                    )

                if self._table_exists(conn, "ip_decisions"):
                    deleted["ip_decisions"] = _execute_with_changes(
                        conn,
                        "DELETE FROM ip_decisions WHERE expires < ?",
                        (ip_decision_cutoff,),
                    )

                if self._table_exists(conn, "unsure_patterns"):
                    deleted["unsure_patterns"] = _execute_with_changes(
                        conn,
                        "DELETE FROM unsure_patterns WHERE timestamp < ?",
                        (unsure_patterns_cutoff,),
                    )

                if self._table_exists(conn, "daily_stats"):
                    deleted["daily_stats"] = _execute_with_changes(
                        conn,
                        "DELETE FROM daily_stats WHERE date < ?",
                        (daily_stats_cutoff,),
                    )

                if self._table_exists(conn, "exact_ip_overrides"):
                    deleted["exact_ip_overrides"] = _execute_with_changes(
                        conn,
                        "DELETE FROM exact_ip_overrides WHERE expires_at IS NOT NULL AND expires_at < ?",
                        (exact_override_cutoff,),
                    )

                if self._table_exists(conn, "admin_sessions"):
                    deleted["admin_sessions"] = _execute_with_changes(
                        conn,
                        "DELETE FROM admin_sessions WHERE expires_at < ?",
                        (exact_override_cutoff,),
                    )
                if self._table_exists(conn, "admin_totp_challenges"):
                    deleted["admin_totp_challenges"] = _execute_with_changes(
                        conn,
                        "DELETE FROM admin_totp_challenges WHERE expires_at < ?",
                        (exact_override_cutoff,),
                    )

                if self._table_exists(conn, "module_heartbeats"):
                    deleted["module_heartbeats"] = _execute_with_changes(
                        conn,
                        "DELETE FROM module_heartbeats WHERE created_at < ?",
                        (module_heartbeats_cutoff,),
                    )

                if self._table_exists(conn, "ingested_raw_events"):
                    deleted["ingested_raw_events"] = _execute_with_changes(
                        conn,
                        """
                        DELETE FROM ingested_raw_events
                        WHERE COALESCE(processed_at, occurred_at) < ?
                        """,
                        (ingested_raw_events_cutoff,),
                    )

                if self._table_exists(conn, "ip_history"):
                    deleted["ip_history"] = _execute_with_changes(
                        conn,
                        "DELETE FROM ip_history WHERE timestamp < ?",
                        (ip_history_cutoff,),
                    )

                if self._table_exists(conn, "subnet_evidence"):
                    deleted["subnet_evidence"] = _execute_with_changes(
                        conn,
                        "DELETE FROM subnet_evidence WHERE last_updated < ?",
                        (subnet_evidence_cutoff,),
                    )

                if self._table_exists(conn, "violation_history"):
                    deleted["violation_history"] = _execute_with_changes(
                        conn,
                        "DELETE FROM violation_history WHERE timestamp < ?",
                        (violation_history_cutoff,),
                    )

                deleted.setdefault("review_resolutions", 0)
                deleted.setdefault("review_labels", 0)
                deleted.setdefault("review_cases", 0)
                deleted.setdefault("analysis_events_from_cases", 0)
                if self._table_exists(conn, "review_cases"):
                    stale_case_rows = conn.execute(
                        """
                        SELECT id, latest_event_id
                        FROM review_cases
                        WHERE status IN ('RESOLVED', 'SKIPPED') AND updated_at < ?
                        """,
                        (resolved_review_cutoff,),
                    ).fetchall()
                    stale_case_ids = [int(row["id"]) for row in stale_case_rows]
                    stale_event_ids = sorted(
                        {
                            int(row["latest_event_id"])
                            for row in stale_case_rows
                            if row["latest_event_id"] is not None
                        }
                    )
                    if stale_case_ids:
                        case_placeholders = ", ".join("?" for _ in stale_case_ids)
                        if self._table_exists(conn, "review_resolutions"):
                            deleted["review_resolutions"] = _execute_with_changes(
                                conn,
                                f"DELETE FROM review_resolutions WHERE case_id IN ({case_placeholders})",
                                tuple(stale_case_ids),
                            )
                        if self._table_exists(conn, "review_labels"):
                            deleted["review_labels"] = _execute_with_changes(
                                conn,
                                f"DELETE FROM review_labels WHERE case_id IN ({case_placeholders})",
                                tuple(stale_case_ids),
                            )
                        deleted["review_cases"] = _execute_with_changes(
                            conn,
                            f"DELETE FROM review_cases WHERE id IN ({case_placeholders})",
                            tuple(stale_case_ids),
                        )
                        if stale_event_ids and self._table_exists(conn, "analysis_events"):
                            event_placeholders = ", ".join("?" for _ in stale_event_ids)
                            deleted["analysis_events_from_cases"] = _execute_with_changes(
                                conn,
                                f"""
                                DELETE FROM analysis_events
                                WHERE id IN ({event_placeholders})
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM review_cases rc
                                      WHERE rc.latest_event_id = analysis_events.id
                                  )
                                """,
                                tuple(stale_event_ids),
                            )

                deleted.setdefault("orphan_analysis_events", 0)
                if self._table_exists(conn, "analysis_events"):
                    deleted["orphan_analysis_events"] = _execute_with_changes(
                        conn,
                        """
                        DELETE FROM analysis_events
                        WHERE created_at < ?
                          AND NOT EXISTS (
                              SELECT 1
                              FROM review_cases rc
                              WHERE rc.latest_event_id = analysis_events.id
                          )
                        """,
                        (orphan_analysis_events_cutoff,),
                    )

                conn.commit()
                checkpoint_mode = "TRUNCATE" if normalized_mode == "emergency" else "PASSIVE"
                checkpoint_row = conn.execute(f"PRAGMA wal_checkpoint({checkpoint_mode})").fetchone()
                conn.commit()
        except sqlite3.OperationalError as exc:
            if not is_sqlite_busy_error(exc):
                raise
            logger.info("DB maintenance skipped: mode=%s reason=database_locked", normalized_mode)
            report["skipped"] = True
            report["skip_reason"] = "database_locked"
            report["deleted"] = {}
            return report

        report["wal_checkpoint"] = list(checkpoint_row) if checkpoint_row else []
        if normalized_mode == "emergency":
            try:
                with self._maintenance_connect() as conn:
                    conn.execute("VACUUM")
                    conn.commit()
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    report["vacuumed"] = True
            except sqlite3.OperationalError as exc:
                if not is_sqlite_busy_error(exc):
                    raise
                logger.info("DB maintenance skipped: mode=%s reason=database_locked", normalized_mode)
                report["skipped"] = True
                report["skip_reason"] = "database_locked"
        return report

    def create_admin_session(self, payload: dict[str, Any], session_ttl_hours: int = 24) -> dict[str, Any]:
        return self.sessions.create(payload, session_ttl_hours=session_ttl_hours)

    def get_admin_session(self, token: str) -> Optional[dict[str, Any]]:
        return self.sessions.get(token)

    def delete_admin_session(self, token: str) -> None:
        self.sessions.delete(token)

    def upsert_admin_identity(
        self,
        *,
        subject: str,
        auth_method: str,
        role: str,
        telegram_id: int | None = None,
        username: str | None = None,
        first_name: str | None = None,
    ) -> dict[str, Any]:
        return self.admin_security.upsert_identity(
            subject=subject,
            auth_method=auth_method,
            role=role,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )

    def get_admin_identity(self, subject: str) -> Optional[dict[str, Any]]:
        return self.admin_security.get_identity(subject)

    def set_admin_identity_totp(self, subject: str, *, secret_cipher: str, enabled: bool) -> dict[str, Any]:
        return self.admin_security.set_identity_totp(subject, secret_cipher=secret_cipher, enabled=enabled)

    def create_admin_totp_challenge(
        self,
        *,
        subject: str,
        auth_method: str,
        role: str,
        telegram_id: int | None = None,
        username: str | None = None,
        first_name: str | None = None,
        challenge_kind: str,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        return self.admin_security.create_totp_challenge(
            subject=subject,
            auth_method=auth_method,
            role=role,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            challenge_kind=challenge_kind,
            ttl_seconds=ttl_seconds,
        )

    def get_admin_totp_challenge(self, token: str) -> Optional[dict[str, Any]]:
        return self.admin_security.get_totp_challenge(token)

    def update_admin_totp_challenge_secret(self, token: str, secret_cipher: str) -> dict[str, Any]:
        return self.admin_security.update_totp_challenge_secret(token, secret_cipher)

    def delete_admin_totp_challenge(self, token: str) -> None:
        self.admin_security.delete_totp_challenge(token)

    def record_admin_audit_event(
        self,
        *,
        actor_subject: str,
        actor_role: str,
        actor_auth_method: str,
        actor_telegram_id: int | None,
        actor_username: str | None,
        action: str,
        target_type: str,
        target_id: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.admin_security.record_audit_event(
            actor_subject=actor_subject,
            actor_role=actor_role,
            actor_auth_method=actor_auth_method,
            actor_telegram_id=actor_telegram_id,
            actor_username=actor_username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )

    def list_admin_audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return self.admin_security.list_audit_events(limit=limit)

    def update_service_heartbeat(
        self,
        service_name: str,
        status: str = "ok",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.health.update_heartbeat(service_name, status=status, details=details)

    def get_service_heartbeat(self, service_name: str, stale_after_seconds: int = 60) -> dict[str, Any]:
        return self.health.get_heartbeat(service_name, stale_after_seconds=stale_after_seconds)

    def get_health_snapshot(self, *, fast_read: bool = False) -> dict[str, Any]:
        return self._ttl_cache_get(
            "health",
            10.0,
            lambda: self.health.get_snapshot(
                live_rules_state_loader=lambda: self.get_live_rules_state(skip_db_mirror=True),
                timeout=FAST_READ_SQLITE_TIMEOUT_SECONDS if fast_read else None,
                busy_timeout_ms=FAST_READ_SQLITE_BUSY_TIMEOUT_MS if fast_read else None,
                query_time_limit_ms=FAST_READ_SQLITE_QUERY_LIMIT_MS if fast_read else None,
            ),
            allow_stale_on_busy=fast_read,
        )

    def is_admin_tg_id(self, tg_id: int) -> bool:
        return self.get_admin_role_for_tg_id(tg_id) is not None

    def get_admin_role_for_tg_id(self, tg_id: int) -> str | None:
        rules = self.get_live_rules()
        numeric_id = int(tg_id)
        owner_ids = {int(value) for value in rules.get("admin_tg_ids", self.base_config.get("admin_tg_ids", []))}
        moderator_ids = {
            int(value)
            for value in rules.get("moderator_tg_ids", self.base_config.get("moderator_tg_ids", []))
        }
        viewer_ids = {
            int(value)
            for value in rules.get("viewer_tg_ids", self.base_config.get("viewer_tg_ids", []))
        }
        if numeric_id in owner_ids:
            return "owner"
        if numeric_id in moderator_ids:
            return "moderator"
        if numeric_id in viewer_ids:
            return "viewer"
        return None

    async def async_sync_runtime_config(self, runtime_config: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.sync_runtime_config, runtime_config)

    async def async_get_ip_override(self, ip: str) -> Optional[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_ip_override, ip)

    async def async_set_ip_override(
        self,
        ip: str,
        decision: str,
        source: str,
        actor: str,
        actor_tg_id: Optional[int] = None,
        ttl_days: int = 7,
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self.set_ip_override,
            ip,
            decision,
            source,
            actor,
            actor_tg_id,
            ttl_days,
        )

    async def async_record_analysis_event(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        observation: Optional[dict[str, Any]] = None,
        source_event_uid: str | None = None,
    ) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.record_analysis_event,
            user,
            ip,
            tag,
            bundle,
            observation,
            source_event_uid,
        )

    async def async_ensure_review_case(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        event_id: int,
        review_reason: str,
    ) -> ReviewCaseSummary:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.ensure_review_case,
            user,
            ip,
            tag,
            bundle,
            event_id,
            review_reason,
        )

    async def async_recheck_review_case(
        self,
        case_id: int,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        review_reason: str | None,
        actor: str,
        actor_tg_id: Optional[int] = None,
        note: str = "",
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.recheck_review_case,
            case_id,
            user,
            ip,
            tag,
            bundle,
            review_reason,
            actor,
            actor_tg_id,
            note,
        )

    async def async_promote_learning_patterns(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.promote_learning_patterns)

    async def async_get_promoted_pattern(
        self, pattern_type: str, pattern_value: str
    ) -> Optional[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_promoted_pattern, pattern_type, pattern_value)

    async def async_update_service_heartbeat(
        self,
        service_name: str,
        status: str = "ok",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.update_service_heartbeat, service_name, status, details)

    async def async_run_db_maintenance(self, mode: str = "periodic") -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run_db_maintenance, mode)
