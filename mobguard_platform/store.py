from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

from .models import DecisionBundle, ReviewCaseSummary
from .asn_sources import detect_asn_source
from .repositories.health import ServiceHealthRepository
from .repositories.sessions import AdminSessionRepository
from .runtime import canonicalize_runtime_bound_settings
from .storage.sqlite import SQLiteStorage


EDITABLE_TOP_LEVEL_KEYS = {
    "pure_mobile_asns": int,
    "pure_home_asns": int,
    "mixed_asns": int,
    "allowed_isp_keywords": str,
    "home_isp_keywords": str,
    "exclude_isp_keywords": str,
    "admin_tg_ids": int,
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
}

DEFAULT_SETTINGS = {
    "shadow_mode": True,
    "probable_home_warning_only": True,
    "auto_enforce_requires_hard_or_multi_signal": True,
    "provider_conflict_review_only": True,
    "review_ui_base_url": "",
    "provider_mobile_marker_bonus": 18,
    "provider_home_marker_penalty": -18,
    "learning_promote_asn_min_support": 10,
    "learning_promote_asn_min_precision": 0.95,
    "learning_promote_combo_min_support": 5,
    "learning_promote_combo_min_precision": 0.90,
    "live_rules_refresh_seconds": 15,
}


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


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
        self.storage = SQLiteStorage(db_path)
        self.sessions = AdminSessionRepository(self.storage)
        self.health = ServiceHealthRepository(self.storage, db_path)

    def _connect(self) -> sqlite3.Connection:
        return self.storage.connect()

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

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
                    int(meta.get("revision", 1)),
                    meta.get("updated_at", ""),
                    "system" if meta.get("updated_by") == "bootstrap" else meta.get("updated_by", "system"),
                ),
            )
            conn.commit()

    def init_schema(self) -> None:
        seed_rules = self.build_seed_rules()
        with self._connect() as conn:
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
                    occurred_at TEXT NOT NULL,
                    log_offset INTEGER,
                    subject_uuid TEXT,
                    username TEXT,
                    system_id INTEGER,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    raw_payload_json TEXT NOT NULL,
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
                    module_id TEXT,
                    module_name TEXT,
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
                    punitive_eligible INTEGER NOT NULL DEFAULT 0,
                    latest_event_id INTEGER NOT NULL,
                    repeat_count INTEGER NOT NULL DEFAULT 1,
                    reason_codes_json TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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
                CREATE TABLE IF NOT EXISTS service_heartbeats (
                    service_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(ip_decisions)").fetchall()
            }
            if columns and "bundle_json" not in columns:
                conn.execute("ALTER TABLE ip_decisions ADD COLUMN bundle_json TEXT")
            analysis_event_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(analysis_events)").fetchall()
            }
            if analysis_event_columns and "module_id" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN module_id TEXT")
            if analysis_event_columns and "module_name" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN module_name TEXT")
            if analysis_event_columns and "system_id" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN system_id INTEGER")
            if analysis_event_columns and "score" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN score INTEGER NOT NULL DEFAULT 0")
            if analysis_event_columns and "isp" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN isp TEXT")
            if analysis_event_columns and "asn" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN asn INTEGER")
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
            if review_case_columns and "punitive_eligible" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN punitive_eligible INTEGER NOT NULL DEFAULT 0")
            if review_case_columns and "system_id" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN system_id INTEGER")
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
                "CREATE INDEX IF NOT EXISTS idx_review_cases_status ON review_cases(status, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_opened_at ON review_cases(opened_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_module_id ON review_cases(module_id, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_system_id ON review_cases(system_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_telegram_id ON review_cases(telegram_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_system_id ON analysis_events(system_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_module_id ON analysis_events(module_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_events_ip ON analysis_events(ip, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_labels_pattern ON review_labels(pattern_type, pattern_value)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unsure_learning_pattern ON unsure_learning(pattern_type, pattern_value)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_sessions_exp ON admin_sessions(expires_at)"
            )

            live_rules = conn.execute("SELECT rules_json FROM live_rules WHERE id = 1").fetchone()
            if not live_rules:
                conn.execute(
                    """
                    INSERT INTO live_rules (id, rules_json, revision, updated_at, updated_by)
                    VALUES (1, ?, 1, ?, ?)
                    """,
                    (json.dumps(seed_rules, ensure_ascii=False), _utcnow(), "system"),
                )
            conn.commit()

    def get_module(self, module_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT module_id, module_name, status, version, protocol_version,
                       config_revision_applied, first_seen_at, last_seen_at, install_state, managed,
                       health_status, error_text, last_validation_at, spool_depth, access_log_exists,
                       metadata_json, token_ciphertext
                FROM modules
                WHERE module_id = ?
                """,
                (module_id,),
            ).fetchone()
        if not row:
            return None
        return _apply_module_metadata(dict(row), row["metadata_json"])

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
        normalized_id = str(module_id or "").strip()
        normalized_name = str(module_name or "").strip()
        if not normalized_id:
            raise ValueError("module_id is required")
        if not normalized_name:
            raise ValueError("module_name is required")
        if not token:
            raise ValueError("module token is required")
        now = _utcnow()
        token_hash = _sha256_hex(token)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM modules WHERE module_id = ?",
                (normalized_id,),
            ).fetchone()
            if existing:
                raise ValueError("Module already exists")
            conn.execute(
                """
                INSERT INTO modules (
                    module_id, module_name, token_hash, token_ciphertext, status, version, protocol_version,
                    config_revision_applied, first_seen_at, last_seen_at, install_state, managed, metadata_json
                ) VALUES (?, ?, ?, ?, 'pending_install', '', ?, 0, ?, '', 'pending_install', 1, ?)
                """,
                (
                    normalized_id,
                    normalized_name,
                    token_hash,
                    str(token_ciphertext or "").strip(),
                    str(protocol_version or "v1").strip() or "v1",
                    now,
                    metadata_json,
                ),
            )
            conn.commit()
        module = self.get_module(normalized_id)
        if not module:
            raise ValueError("Failed to persist module")
        return module

    def update_managed_module(
        self,
        module_id: str,
        *,
        module_name: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized_id = str(module_id or "").strip()
        normalized_name = str(module_name or "").strip()
        if not normalized_name:
            raise ValueError("module_name is required")
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT managed FROM modules WHERE module_id = ?",
                (normalized_id,),
            ).fetchone()
            if not row:
                raise ValueError("Module is not registered")
            conn.execute(
                """
                UPDATE modules
                SET module_name = ?, metadata_json = ?
                WHERE module_id = ?
                """,
                (
                    normalized_name,
                    metadata_json,
                    normalized_id,
                ),
            )
            conn.commit()
        module = self.get_module(normalized_id)
        if not module:
            raise ValueError("Module is not registered")
        return module

    def get_module_token_ciphertext(self, module_id: str) -> str:
        normalized_id = str(module_id or "").strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token_ciphertext FROM modules WHERE module_id = ?",
                (normalized_id,),
            ).fetchone()
        if not row:
            raise ValueError("Module is not registered")
        ciphertext = str(row["token_ciphertext"] or "").strip()
        if not ciphertext:
            raise ValueError("Module token reveal is unavailable for this module")
        return ciphertext

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
        normalized_id = str(module_id or "").strip()
        normalized_name = str(module_name or "").strip()
        if not normalized_id:
            raise ValueError("module_id is required")
        if not token:
            raise ValueError("module token is required")
        now = _utcnow()
        token_hash = _sha256_hex(token)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT token_hash, module_name, metadata_json FROM modules WHERE module_id = ?",
                (normalized_id,),
            ).fetchone()
            if existing:
                if str(existing["token_hash"]) != token_hash:
                    raise ValueError("Invalid module token")
                stored_metadata = _module_metadata_from_json(existing["metadata_json"])
                effective_metadata = stored_metadata if metadata is None else {**stored_metadata, **metadata}
                conn.execute(
                    """
                    UPDATE modules
                    SET module_name = ?, status = 'online', version = ?, protocol_version = ?,
                        config_revision_applied = ?, last_seen_at = ?, install_state = 'online', metadata_json = ?
                    WHERE module_id = ?
                    """,
                    (
                        normalized_name or str(existing["module_name"] or normalized_id).strip() or normalized_id,
                        str(version or "").strip(),
                        str(protocol_version or "v1").strip() or "v1",
                        int(config_revision_applied or 0),
                        now,
                        json.dumps(effective_metadata, ensure_ascii=False),
                        normalized_id,
                    ),
                )
            else:
                if not auto_create:
                    raise ValueError("Module is not registered")
                metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
                conn.execute(
                    """
                    INSERT INTO modules (
                        module_id, module_name, token_hash, token_ciphertext, status, version, protocol_version,
                        config_revision_applied, first_seen_at, last_seen_at, install_state, managed, metadata_json
                    ) VALUES (?, ?, ?, '', 'online', ?, ?, ?, ?, ?, 'online', 0, ?)
                    """,
                    (
                        normalized_id,
                        normalized_name or normalized_id,
                        token_hash,
                        str(version or "").strip(),
                        str(protocol_version or "v1").strip() or "v1",
                        int(config_revision_applied or 0),
                        now,
                        now,
                        metadata_json,
                    ),
                )
            conn.commit()
        module = self.get_module(normalized_id)
        if not module:
            raise ValueError("Failed to persist module")
        return module

    def authenticate_module(self, module_id: str, token: str) -> dict[str, Any]:
        normalized_id = str(module_id or "").strip()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT module_id, module_name, token_hash, token_ciphertext, status, version, protocol_version,
                       config_revision_applied, first_seen_at, last_seen_at, install_state, managed,
                       health_status, error_text, last_validation_at, spool_depth, access_log_exists,
                       metadata_json
                FROM modules
                WHERE module_id = ?
                """,
                (normalized_id,),
            ).fetchone()
        if not row or str(row["token_hash"]) != _sha256_hex(token):
            raise ValueError("Invalid module credentials")
        payload = dict(row)
        payload.pop("token_hash", None)
        return _apply_module_metadata(payload, row["metadata_json"])

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
        normalized_id = str(module_id or "").strip()
        now = _utcnow()
        details_payload = dict(details or {})
        details_json = json.dumps(details_payload, ensure_ascii=False)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT module_name, health_status, error_text, last_validation_at, spool_depth, access_log_exists
                FROM modules WHERE module_id = ?
                """,
                (normalized_id,),
            ).fetchone()
            if not row:
                raise ValueError("Module is not registered")
            health_status, error_text, last_validation_at, spool_depth, access_log_exists = _module_health_snapshot(
                details_payload,
                current_status=row["health_status"] if row else "warn",
                current_error_text=row["error_text"] if row else "",
                current_last_validation_at=row["last_validation_at"] if row else "",
                current_spool_depth=row["spool_depth"] if row else 0,
                current_access_log_exists=row["access_log_exists"] if row else 0,
            )
            conn.execute(
                """
                UPDATE modules
                SET status = ?, version = ?, protocol_version = ?, config_revision_applied = ?, last_seen_at = ?, install_state = 'online',
                    health_status = ?, error_text = ?, last_validation_at = ?, spool_depth = ?, access_log_exists = ?
                WHERE module_id = ?
                """,
                (
                    str(status or "online").strip() or "online",
                    str(version or "").strip(),
                    str(protocol_version or "v1").strip() or "v1",
                    int(config_revision_applied or 0),
                    now,
                    health_status,
                    error_text,
                    last_validation_at,
                    spool_depth,
                    access_log_exists,
                    normalized_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO module_heartbeats (
                    module_id, status, version, protocol_version, config_revision_applied, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_id,
                    str(status or "online").strip() or "online",
                    str(version or "").strip(),
                    str(protocol_version or "v1").strip() or "v1",
                    int(config_revision_applied or 0),
                    details_json,
                    now,
                ),
            )
            conn.commit()
        module = self.get_module(normalized_id)
        if not module:
            raise ValueError("Module is not registered")
        return module

    def list_modules(self, stale_after_seconds: int = 180) -> list[dict[str, Any]]:
        now = datetime.utcnow().replace(microsecond=0)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.module_id, m.module_name, m.status, m.version, m.protocol_version,
                       m.config_revision_applied, m.first_seen_at, m.last_seen_at, m.install_state,
                       m.managed, m.health_status, m.error_text, m.last_validation_at,
                       m.spool_depth, m.access_log_exists, m.metadata_json,
                       (
                           SELECT COUNT(*)
                           FROM review_cases rc
                           WHERE rc.module_id = m.module_id AND rc.status = 'OPEN'
                       ) AS open_review_cases,
                       (
                           SELECT COUNT(*)
                           FROM analysis_events ae
                           WHERE ae.module_id = m.module_id
                       ) AS analysis_events_count
                FROM modules m
                ORDER BY m.last_seen_at DESC, m.module_id ASC
                """
            ).fetchall()
        items: list[dict[str, Any]] = []
        stale_delta = timedelta(seconds=stale_after_seconds)
        for row in rows:
            payload = dict(row)
            last_seen_raw = str(payload.get("last_seen_at") or "")
            last_seen = datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
            payload = _apply_module_metadata(payload, row["metadata_json"])
            payload["healthy"] = bool(last_seen and now - last_seen <= stale_delta)
            items.append(payload)
        return items

    def ingest_raw_event(
        self,
        module_id: str,
        module_name: str,
        event_uid: str,
        occurred_at: str,
        payload: dict[str, Any],
    ) -> bool:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM ingested_raw_events WHERE event_uid = ?",
                (event_uid,),
            ).fetchone()
            if existing:
                return False
            conn.execute(
                """
                INSERT INTO ingested_raw_events (
                    event_uid, module_id, module_name, occurred_at, log_offset,
                    subject_uuid, username, system_id, telegram_id, ip, tag, raw_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_uid,
                    module_id,
                    module_name,
                    occurred_at,
                    payload.get("log_offset"),
                    payload.get("uuid"),
                    payload.get("username"),
                    payload.get("system_id"),
                    payload.get("telegram_id"),
                    payload.get("ip"),
                    payload.get("tag"),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
            return True

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
                SET processed_at = ?, analysis_event_id = ?, review_case_id = ?
                WHERE event_uid = ?
                """,
                (_utcnow(), analysis_event_id, review_case_id, event_uid),
            )
            conn.commit()

    def get_live_rules(self) -> dict[str, Any]:
        return self.get_live_rules_state()["rules"]

    def get_live_rules_state(self) -> dict[str, Any]:
        payload, meta = self._load_rules_from_file()
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
    ) -> int:
        now = _utcnow()
        payload = bundle.to_dict()
        module_id = str((user or {}).get("module_id") or "").strip() or None
        module_name = str((user or {}).get("module_name") or "").strip() or module_id
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn, punitive_eligible,
                    reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    module_id,
                    module_name,
                    (user or {}).get("uuid"),
                    (user or {}).get("username"),
                    _coerce_optional_int((user or {}).get("id")),
                    str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                    ip,
                    tag,
                    bundle.verdict,
                    bundle.confidence_band,
                    bundle.score,
                    bundle.isp,
                    bundle.asn,
                    int(bundle.punitive_eligible),
                    json.dumps([reason.to_dict() for reason in bundle.reasons], ensure_ascii=False),
                    json.dumps(bundle.signal_flags, ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def build_review_url(self, case_id: int) -> str:
        base_url = str(self.get_live_rules().get("settings", {}).get("review_ui_base_url", "")).rstrip("/")
        if not base_url:
            base_url = str(self.base_config.get("settings", {}).get("review_ui_base_url", "")).rstrip("/")
        if not base_url:
            return ""
        return f"{base_url}/reviews/{case_id}"

    def ensure_review_case(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        event_id: int,
        review_reason: str,
    ) -> ReviewCaseSummary:
        now = _utcnow()
        module_id = str((user or {}).get("module_id") or "").strip()
        module_name = str((user or {}).get("module_name") or "").strip() or module_id
        unique_key = f"{module_id or 'legacy'}:{(user or {}).get('uuid', 'unknown')}:{ip}:{tag}"
        reason_codes = json.dumps(bundle.reason_codes, ensure_ascii=False)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, repeat_count FROM review_cases WHERE unique_key = ? AND module_id = ?",
                (unique_key, module_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE review_cases
                    SET status = 'OPEN',
                        review_reason = ?,
                        module_name = ?,
                        username = ?,
                        system_id = ?,
                        telegram_id = ?,
                        verdict = ?,
                        confidence_band = ?,
                        score = ?,
                        isp = ?,
                        asn = ?,
                        punitive_eligible = ?,
                        latest_event_id = ?,
                        repeat_count = ?,
                        reason_codes_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        review_reason,
                        module_name,
                        (user or {}).get("username"),
                        _coerce_optional_int((user or {}).get("id")),
                        str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                        bundle.verdict,
                        bundle.confidence_band,
                        bundle.score,
                        bundle.isp,
                        bundle.asn,
                        int(bundle.punitive_eligible),
                        event_id,
                        int(existing["repeat_count"]) + 1,
                        reason_codes,
                        now,
                        existing["id"],
                    ),
                )
                case_id = int(existing["id"])
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO review_cases (
                        unique_key, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                        verdict, confidence_band, score, isp, asn, punitive_eligible, latest_event_id, repeat_count,
                        reason_codes_json, opened_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unique_key,
                        "OPEN",
                        review_reason,
                        module_id,
                        module_name,
                        (user or {}).get("uuid"),
                        (user or {}).get("username"),
                        _coerce_optional_int((user or {}).get("id")),
                        str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                        ip,
                        tag,
                        bundle.verdict,
                        bundle.confidence_band,
                        bundle.score,
                        bundle.isp,
                        bundle.asn,
                        int(bundle.punitive_eligible),
                        event_id,
                        1,
                        reason_codes,
                        now,
                        now,
                    ),
                )
                case_id = int(cursor.lastrowid)
            conn.commit()
        summary = self.get_review_case(case_id)
        return ReviewCaseSummary(
            id=summary["id"],
            status=summary["status"],
            review_reason=summary["review_reason"],
            module_id=summary.get("module_id") or "",
            module_name=summary.get("module_name") or "",
            uuid=summary.get("uuid") or "",
            username=summary.get("username") or "",
            system_id=summary.get("system_id"),
            telegram_id=summary.get("telegram_id"),
            ip=summary["ip"],
            tag=summary.get("tag") or "",
            verdict=summary["verdict"],
            confidence_band=summary["confidence_band"],
            score=summary["score"],
            isp=summary.get("isp") or "",
            asn=summary.get("asn"),
            repeat_count=summary["repeat_count"],
            reason_codes=summary.get("reason_codes", []),
            updated_at=summary.get("updated_at", ""),
            review_url=summary.get("review_url", ""),
        )

    def list_review_cases(self, filters: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        filters = filters or {}
        page = max(int(filters.get("page", 1) or 1), 1)
        page_size = min(max(int(filters.get("page_size", 25) or 25), 1), 100)
        sort = str(filters.get("sort", "updated_desc") or "updated_desc")
        sort_map = {
            "updated_desc": "updated_at DESC",
            "updated_asc": "updated_at ASC",
            "score_desc": "score DESC",
            "score_asc": "score ASC",
            "repeat_desc": "repeat_count DESC",
            "repeat_asc": "repeat_count ASC",
        }
        order_by = sort_map.get(sort, "updated_at DESC")
        query = [
            """SELECT id, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag, verdict, confidence_band,
               score, isp, asn, punitive_eligible, repeat_count, reason_codes_json, opened_at, updated_at,
               CASE
                   WHEN punitive_eligible = 1 THEN 'critical'
                   WHEN confidence_band = 'HIGH_HOME' THEN 'high'
                   WHEN confidence_band = 'PROBABLE_HOME' THEN 'medium'
                   ELSE 'low'
               END AS severity
               FROM review_cases"""
        ]
        clauses = []
        params: list[Any] = []
        if filters.get("status"):
            clauses.append("status = ?")
            params.append(filters["status"])
        if filters.get("confidence_band"):
            clauses.append("confidence_band = ?")
            params.append(filters["confidence_band"])
        if filters.get("asn") not in (None, ""):
            clauses.append("asn = ?")
            params.append(int(filters["asn"]))
        if filters.get("username"):
            clauses.append("username LIKE ?")
            params.append(f"%{filters['username']}%")
        if filters.get("module_id"):
            clauses.append("module_id = ?")
            params.append(str(filters["module_id"]))
        if filters.get("system_id") not in (None, ""):
            clauses.append("system_id = ?")
            params.append(int(filters["system_id"]))
        if filters.get("telegram_id") not in (None, ""):
            clauses.append("telegram_id = ?")
            params.append(str(filters["telegram_id"]))
        if filters.get("review_reason"):
            clauses.append("review_reason = ?")
            params.append(filters["review_reason"])
        if filters.get("severity"):
            severity = str(filters["severity"])
            if severity == "critical":
                clauses.append("punitive_eligible = 1")
            elif severity == "high":
                clauses.append("punitive_eligible = 0 AND confidence_band = 'HIGH_HOME'")
            elif severity == "medium":
                clauses.append("confidence_band = 'PROBABLE_HOME'")
            elif severity == "low":
                clauses.append("confidence_band = 'UNSURE'")
        if filters.get("punitive_eligible") not in (None, ""):
            clauses.append("punitive_eligible = ?")
            params.append(1 if str(filters["punitive_eligible"]).lower() in {"1", "true", "yes"} else 0)
        if filters.get("repeat_count_min") not in (None, ""):
            clauses.append("repeat_count >= ?")
            params.append(int(filters["repeat_count_min"]))
        if filters.get("repeat_count_max") not in (None, ""):
            clauses.append("repeat_count <= ?")
            params.append(int(filters["repeat_count_max"]))
        if filters.get("opened_from"):
            clauses.append("opened_at >= ?")
            params.append(_parse_day_boundary(filters["opened_from"], end_of_day=False))
        if filters.get("opened_to"):
            clauses.append("opened_at <= ?")
            params.append(_parse_day_boundary(filters["opened_to"], end_of_day=True))
        if filters.get("q"):
            search = f"%{filters['q']}%"
            clauses.append(
                "(ip LIKE ? OR username LIKE ? OR isp LIKE ? OR uuid LIKE ? OR telegram_id LIKE ? OR CAST(system_id AS TEXT) LIKE ?)"
            )
            params.extend([search] * 6)
        if clauses:
            query.append("WHERE " + " AND ".join(clauses))
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        count_sql = f"SELECT COUNT(*) AS cnt FROM review_cases{where_sql}"
        query.append(f"ORDER BY {order_by} LIMIT ? OFFSET ?")
        sql = " ".join(query)
        with self._connect() as conn:
            total = conn.execute(count_sql, params).fetchone()["cnt"]
            rows = conn.execute(sql, [*params, page_size, (page - 1) * page_size]).fetchall()
        items = []
        with self._connect() as conn:
            for row in rows:
                item = _resolve_review_module_name(conn, _normalize_review_identity_payload(dict(row)))
                item["reason_codes"] = json.loads(item.pop("reason_codes_json"))
                item["review_url"] = self.build_review_url(item["id"])
                items.append(item)
        return {
            "items": items,
            "count": total,
            "page": page,
            "page_size": page_size,
        }

    def get_review_case(self, case_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            case_row = conn.execute(
                """
                SELECT * FROM review_cases WHERE id = ?
                """,
                (case_id,),
            ).fetchone()
            if not case_row:
                raise KeyError(f"Review case {case_id} not found")
            event_row = conn.execute(
                "SELECT * FROM analysis_events WHERE id = ?",
                (case_row["latest_event_id"],),
            ).fetchone()
            resolutions = conn.execute(
                """
                SELECT id, resolution, actor, actor_tg_id, note, created_at
                FROM review_resolutions
                WHERE case_id = ?
                ORDER BY created_at DESC
                """,
                (case_id,),
            ).fetchall()
            related_cases = conn.execute(
                """
                SELECT id, status, module_id, module_name, ip, verdict, confidence_band, updated_at, username, uuid, system_id, telegram_id
                FROM review_cases
                WHERE id != ? AND (uuid = ? OR ip = ?)
                ORDER BY updated_at DESC
                LIMIT 10
                """,
                (case_id, case_row["uuid"], case_row["ip"]),
            ).fetchall()
        with self._connect() as conn:
            case = _resolve_review_module_name(conn, _normalize_review_identity_payload(dict(case_row)))
        case["reason_codes"] = json.loads(case.pop("reason_codes_json"))
        event_payload = dict(event_row) if event_row else {}
        if event_payload:
            event_payload["reasons"] = json.loads(event_payload.pop("reasons_json"))
            event_payload["signal_flags"] = json.loads(event_payload.pop("signal_flags_json"))
            event_payload["bundle"] = json.loads(event_payload.pop("bundle_json"))
        case["latest_event"] = event_payload
        case["resolutions"] = [dict(row) for row in resolutions]
        with self._connect() as conn:
            case["related_cases"] = [
                _resolve_review_module_name(conn, _normalize_review_identity_payload(dict(row)))
                for row in related_cases
            ]
        case["review_url"] = self.build_review_url(case_id)
        return case

    def _record_labels_for_resolution(
        self,
        conn: sqlite3.Connection,
        case_id: int,
        event_id: int,
        bundle: DecisionBundle,
        decision: str,
    ) -> None:
        labels: set[tuple[str, str]] = set()
        if bundle.asn:
            labels.add(("asn", str(bundle.asn)))
        provider_evidence = bundle.signal_flags.get("provider_evidence")
        if isinstance(provider_evidence, dict):
            provider_key = str(provider_evidence.get("provider_key") or "").strip().lower()
            service_type_hint = str(provider_evidence.get("service_type_hint") or "").strip().lower()
            if provider_key:
                labels.add(("provider", provider_key))
                if service_type_hint and service_type_hint != "unknown":
                    labels.add(("provider_service", f"{provider_key}:{service_type_hint}"))
        for reason in bundle.reasons:
            metadata = reason.metadata or {}
            for keyword in metadata.get("keywords", []):
                labels.add(("keyword", str(keyword)))
            if metadata.get("combo_key"):
                labels.add(("combo", str(metadata["combo_key"])))
            if metadata.get("ptr_domain"):
                labels.add(("ptr_domain", str(metadata["ptr_domain"])))
            if metadata.get("subnet"):
                labels.add(("subnet", str(metadata["subnet"])))

        now = _utcnow()
        for pattern_type, pattern_value in labels:
            conn.execute(
                """
                INSERT OR IGNORE INTO review_labels (case_id, event_id, pattern_type, pattern_value, decision, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (case_id, event_id, pattern_type, pattern_value, decision, now),
            )

    def promote_learning_patterns(self) -> None:
        live_rules = self.get_live_rules()
        settings = live_rules.get("settings", {})
        asn_min_support = int(settings.get("learning_promote_asn_min_support", 10))
        asn_min_precision = float(settings.get("learning_promote_asn_min_precision", 0.95))
        combo_min_support = int(settings.get("learning_promote_combo_min_support", 5))
        combo_min_precision = float(settings.get("learning_promote_combo_min_precision", 0.90))

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pattern_type, pattern_value, decision, COUNT(*) AS support
                FROM review_labels
                GROUP BY pattern_type, pattern_value, decision
                """
            ).fetchall()
            stats: dict[tuple[str, str], dict[str, int]] = {}
            for row in rows:
                key = (row["pattern_type"], row["pattern_value"])
                stats.setdefault(key, {})
                stats[key][row["decision"]] = int(row["support"])

            conn.execute("DELETE FROM learning_pattern_stats")
            conn.execute("DELETE FROM learning_patterns_active")
            now = _utcnow()
            for (pattern_type, pattern_value), decision_counts in stats.items():
                total = sum(decision_counts.values())
                best_decision = None
                best_support = -1
                best_precision = -1.0
                ambiguous = False
                for decision, support in decision_counts.items():
                    precision = support / total if total else 0.0
                    conn.execute(
                        """
                        INSERT INTO learning_pattern_stats (
                            pattern_type, pattern_value, decision, support, total, precision, updated_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pattern_type,
                            pattern_value,
                            decision,
                            support,
                            total,
                            precision,
                            now,
                            json.dumps({"counts": decision_counts}, ensure_ascii=False),
                        ),
                    )
                    if support > best_support or (
                        support == best_support and precision > best_precision
                    ):
                        best_decision = decision
                        best_support = support
                        best_precision = precision
                        ambiguous = False
                    elif support == best_support and abs(precision - best_precision) < 1e-9:
                        ambiguous = True

                if ambiguous or not best_decision:
                    continue
                if pattern_type == "asn":
                    min_support = asn_min_support
                    min_precision = asn_min_precision
                else:
                    min_support = combo_min_support
                    min_precision = combo_min_precision

                if best_support >= min_support and best_precision >= min_precision:
                    conn.execute(
                        """
                        INSERT INTO learning_patterns_active (
                            pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pattern_type,
                            pattern_value,
                            best_decision,
                            best_support,
                            best_precision,
                            now,
                            json.dumps({"total": total}, ensure_ascii=False),
                        ),
                    )
            conn.commit()

    def get_promoted_pattern(self, pattern_type: str, pattern_value: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT pattern_type, pattern_value, decision, support, precision, metadata_json
                FROM learning_patterns_active
                WHERE pattern_type = ? AND pattern_value = ?
                """,
                (pattern_type, pattern_value),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["metadata"] = json.loads(payload.pop("metadata_json"))
        return payload

    def resolve_review_case(
        self,
        case_id: int,
        resolution: str,
        actor: str,
        actor_tg_id: Optional[int] = None,
        note: str = "",
    ) -> dict[str, Any]:
        if resolution not in {"MOBILE", "HOME", "SKIP"}:
            raise ValueError("Resolution must be MOBILE, HOME or SKIP")

        with self._connect() as conn:
            case_row = conn.execute(
                "SELECT * FROM review_cases WHERE id = ?",
                (case_id,),
            ).fetchone()
            if not case_row:
                raise KeyError(f"Review case {case_id} not found")
            event_row = conn.execute(
                "SELECT bundle_json, ip FROM analysis_events WHERE id = ?",
                (case_row["latest_event_id"],),
            ).fetchone()
            now = _utcnow()
            conn.execute(
                """
                INSERT INTO review_resolutions (case_id, event_id, resolution, actor, actor_tg_id, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (case_id, case_row["latest_event_id"], resolution, actor, actor_tg_id, note, now),
            )
            status = "RESOLVED" if resolution in {"MOBILE", "HOME"} else "SKIPPED"
            conn.execute(
                """
                UPDATE review_cases
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, now, case_id),
            )
            if resolution == "SKIP":
                conn.execute(
                    """
                    DELETE FROM exact_ip_overrides
                    WHERE ip = ? AND source = 'review_resolution'
                    """,
                    (event_row["ip"],),
                )
                conn.execute(
                    """
                    DELETE FROM review_labels
                    WHERE case_id = ?
                    """,
                    (case_id,),
                )
            else:
                expires_at = (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat()
                conn.execute(
                    """
                    INSERT INTO exact_ip_overrides (ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at)
                    VALUES (?, ?, 'review_resolution', ?, ?, ?, ?, ?)
                    ON CONFLICT(ip) DO UPDATE SET
                        decision = excluded.decision,
                        source = excluded.source,
                        actor = excluded.actor,
                        actor_tg_id = excluded.actor_tg_id,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (event_row["ip"], resolution, actor, actor_tg_id, now, now, expires_at),
                )
                bundle = DecisionBundle.from_dict(json.loads(event_row["bundle_json"]))
                self._record_labels_for_resolution(conn, case_id, case_row["latest_event_id"], bundle, resolution)
            conn.commit()

        if resolution in {"HOME", "MOBILE"}:
            self.promote_learning_patterns()
        return self.get_review_case(case_id)

    def get_quality_metrics(self, module_id: str | None = None) -> dict[str, Any]:
        live_rules_state = self.get_live_rules_state()
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
        module_filter = str(module_id or "").strip()
        review_case_where = "WHERE module_id = ?" if module_filter else ""
        review_case_params: tuple[Any, ...] = (module_filter,) if module_filter else ()
        open_case_where = "WHERE status = 'OPEN' AND module_id = ?" if module_filter else "WHERE status = 'OPEN'"
        open_case_params: tuple[Any, ...] = (module_filter,) if module_filter else ()
        resolution_join = (
            "FROM review_resolutions rr JOIN review_cases rc ON rc.id = rr.case_id WHERE rc.module_id = ?"
            if module_filter
            else "FROM review_resolutions"
        )
        resolution_params: tuple[Any, ...] = (module_filter,) if module_filter else ()
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
                """
                SELECT rc.review_reason, rc.verdict, ae.bundle_json
                FROM review_cases rc
                JOIN analysis_events ae ON ae.id = rc.latest_event_id
                WHERE rc.status = 'OPEN'
                {module_sql}
                """.format(module_sql="AND rc.module_id = ?" if module_filter else ""),
                open_case_params,
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
            try:
                bundle_payload = json.loads(row["bundle_json"] or "{}")
            except json.JSONDecodeError:
                continue
            signal_flags = bundle_payload.get("signal_flags", {})
            if not isinstance(signal_flags, dict):
                continue
            evidence = signal_flags.get("provider_evidence", {})
            if not isinstance(evidence, dict):
                continue
            if str(evidence.get("provider_classification") or "").lower() != "mixed":
                continue
            provider_key = str(evidence.get("provider_key") or "").strip().lower()
            if not provider_key:
                continue
            mixed_provider_open_cases += 1
            conflict_case = bool(evidence.get("service_conflict")) or str(row["review_reason"]) == "provider_conflict"
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

    def create_admin_session(self, payload: dict[str, Any], session_ttl_hours: int = 24) -> dict[str, Any]:
        return self.sessions.create(payload, session_ttl_hours=session_ttl_hours)

    def get_admin_session(self, token: str) -> Optional[dict[str, Any]]:
        return self.sessions.get(token)

    def delete_admin_session(self, token: str) -> None:
        self.sessions.delete(token)

    def update_service_heartbeat(
        self,
        service_name: str,
        status: str = "ok",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.health.update_heartbeat(service_name, status=status, details=details)

    def get_service_heartbeat(self, service_name: str, stale_after_seconds: int = 60) -> dict[str, Any]:
        return self.health.get_heartbeat(service_name, stale_after_seconds=stale_after_seconds)

    def get_health_snapshot(self) -> dict[str, Any]:
        return self.health.get_snapshot(live_rules_state_loader=self.get_live_rules_state)

    def is_admin_tg_id(self, tg_id: int) -> bool:
        rules = self.get_live_rules()
        admin_ids = rules.get("admin_tg_ids", self.base_config.get("admin_tg_ids", []))
        return int(tg_id) in [int(value) for value in admin_ids]

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
    ) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.record_analysis_event, user, ip, tag, bundle)

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
