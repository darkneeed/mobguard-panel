from __future__ import annotations

import asyncio
import copy
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

from .auth import issue_session_token
from .models import DecisionBundle, ReviewCaseSummary
from .asn_sources import detect_asn_source
from .runtime_paths import canonicalize_runtime_bound_settings


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

LEGACY_EDITABLE_SETTING_ALIASES = {
    "mobile_score_threshold": "threshold_mobile",
}

EDITABLE_SETTINGS_KEYS = {
    "pure_asn_score": (int, float),
    "mixed_asn_score": (int, float),
    "ptr_home_penalty": (int, float),
    "mobile_kw_bonus": (int, float),
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
    "review_ui_base_url": "",
    "learning_promote_asn_min_support": 10,
    "learning_promote_asn_min_precision": 0.95,
    "learning_promote_combo_min_support": 5,
    "learning_promote_combo_min_precision": 0.90,
    "live_rules_refresh_seconds": 15,
}


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


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

    if "settings" in payload:
        settings = payload["settings"]
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        normalized["settings"] = _normalize_settings_for_storage(settings)

    unsupported = set(payload) - set(EDITABLE_TOP_LEVEL_KEYS) - {"settings"}
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

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

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
                CREATE TABLE IF NOT EXISTS analysis_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
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
            if analysis_event_columns and "system_id" not in analysis_event_columns:
                conn.execute("ALTER TABLE analysis_events ADD COLUMN system_id INTEGER")
            review_case_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(review_cases)").fetchall()
            }
            if review_case_columns and "punitive_eligible" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN punitive_eligible INTEGER NOT NULL DEFAULT 0")
            if review_case_columns and "system_id" not in review_case_columns:
                conn.execute("ALTER TABLE review_cases ADD COLUMN system_id INTEGER")
            live_rules_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(live_rules)").fetchall()
            }
            if live_rules_columns and "revision" not in live_rules_columns:
                conn.execute("ALTER TABLE live_rules ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_status ON review_cases(status, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_cases_opened_at ON review_cases(opened_at)"
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
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn, punitive_eligible,
                    reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
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
        unique_key = f"{(user or {}).get('uuid', 'unknown')}:{ip}:{tag}"
        reason_codes = json.dumps(bundle.reason_codes, ensure_ascii=False)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, repeat_count FROM review_cases WHERE unique_key = ?",
                (unique_key,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE review_cases
                    SET status = 'OPEN',
                        review_reason = ?,
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
                        unique_key, status, review_reason, uuid, username, system_id, telegram_id, ip, tag,
                        verdict, confidence_band, score, isp, asn, punitive_eligible, latest_event_id, repeat_count,
                        reason_codes_json, opened_at, updated_at
                    ) VALUES (?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        unique_key,
                        review_reason,
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
            """SELECT id, status, review_reason, uuid, username, system_id, telegram_id, ip, tag, verdict, confidence_band,
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
        for row in rows:
            item = dict(row)
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
                SELECT id, status, ip, verdict, confidence_band, updated_at, username, uuid, system_id, telegram_id
                FROM review_cases
                WHERE id != ? AND (uuid = ? OR ip = ?)
                ORDER BY updated_at DESC
                LIMIT 10
                """,
                (case_id, case_row["uuid"], case_row["ip"]),
            ).fetchall()
        case = dict(case_row)
        case["reason_codes"] = json.loads(case.pop("reason_codes_json"))
        event_payload = dict(event_row) if event_row else {}
        if event_payload:
            event_payload["reasons"] = json.loads(event_payload.pop("reasons_json"))
            event_payload["signal_flags"] = json.loads(event_payload.pop("signal_flags_json"))
            event_payload["bundle"] = json.loads(event_payload.pop("bundle_json"))
        case["latest_event"] = event_payload
        case["resolutions"] = [dict(row) for row in resolutions]
        case["related_cases"] = [dict(row) for row in related_cases]
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

        self.promote_learning_patterns()
        return self.get_review_case(case_id)

    def get_quality_metrics(self) -> dict[str, Any]:
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
        with self._connect() as conn:
            open_cases = conn.execute(
                "SELECT COUNT(*) AS cnt FROM review_cases WHERE status = 'OPEN'"
            ).fetchone()["cnt"]
            total_cases = conn.execute(
                "SELECT COUNT(*) AS cnt FROM review_cases"
            ).fetchone()["cnt"]
            resolved_home = conn.execute(
                "SELECT COUNT(*) AS cnt FROM review_resolutions WHERE resolution = 'HOME'"
            ).fetchone()["cnt"]
            resolved_mobile = conn.execute(
                "SELECT COUNT(*) AS cnt FROM review_resolutions WHERE resolution = 'MOBILE'"
            ).fetchone()["cnt"]
            skipped = conn.execute(
                "SELECT COUNT(*) AS cnt FROM review_resolutions WHERE resolution = 'SKIP'"
            ).fetchone()["cnt"]
            top_noisy = conn.execute(
                """
                SELECT COALESCE(CAST(asn AS TEXT), 'unknown') AS asn_key, COUNT(*) AS cnt
                FROM review_cases
                GROUP BY asn_key
                ORDER BY cnt DESC
                LIMIT 10
                """
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
            "asn_source": asn_source,
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
        token = issue_session_token()
        now = datetime.utcnow().replace(microsecond=0)
        expires_at = now + timedelta(hours=session_ttl_hours)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_sessions (token, telegram_id, username, first_name, payload_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    int(payload["id"]),
                    payload.get("username"),
                    payload.get("first_name"),
                    json.dumps(payload, ensure_ascii=False),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()
        return {
            "token": token,
            "telegram_id": int(payload["id"]),
            "username": payload.get("username"),
            "first_name": payload.get("first_name"),
            "expires_at": expires_at.isoformat(),
        }

    def get_admin_session(self, token: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT token, telegram_id, username, first_name, payload_json, created_at, expires_at
                FROM admin_sessions
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
        if not row:
            return None
        if row["expires_at"] <= _utcnow():
            return None
        payload = dict(row)
        payload["payload"] = json.loads(payload.pop("payload_json"))
        return payload

    def delete_admin_session(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
            conn.commit()

    def update_service_heartbeat(
        self,
        service_name: str,
        status: str = "ok",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO service_heartbeats (service_name, status, details_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(service_name) DO UPDATE SET
                    status = excluded.status,
                    details_json = excluded.details_json,
                    updated_at = excluded.updated_at
                """,
                (service_name, status, json.dumps(details or {}, ensure_ascii=False), now),
            )
            conn.commit()

    def get_service_heartbeat(self, service_name: str, stale_after_seconds: int = 60) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT service_name, status, details_json, updated_at FROM service_heartbeats WHERE service_name = ?",
                (service_name,),
            ).fetchone()
        if not row:
            return {"service_name": service_name, "healthy": False, "status": "missing", "updated_at": ""}
        updated_at = datetime.fromisoformat(row["updated_at"])
        age = (datetime.utcnow() - updated_at).total_seconds()
        return {
            "service_name": row["service_name"],
            "healthy": age <= stale_after_seconds and row["status"] == "ok",
            "status": row["status"],
            "updated_at": row["updated_at"],
            "age_seconds": int(age),
            "details": json.loads(row["details_json"]),
        }

    def get_health_snapshot(self) -> dict[str, Any]:
        live_rules_state = self.get_live_rules_state()
        core_heartbeat = self.get_service_heartbeat("mobguard-core")
        with self._connect() as conn:
            conn.execute("SELECT 1").fetchone()
            admin_sessions = conn.execute(
                "SELECT COUNT(*) AS cnt FROM admin_sessions WHERE expires_at > ?",
                (_utcnow(),),
            ).fetchone()["cnt"]
            analysis_stats = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN score = 0 THEN 1 ELSE 0 END) AS score_zero_count,
                    SUM(CASE WHEN asn IS NULL THEN 1 ELSE 0 END) AS asn_missing_count
                FROM analysis_events
                WHERE created_at >= ?
                """,
                ((datetime.utcnow() - timedelta(hours=24)).replace(microsecond=0).isoformat(),),
            ).fetchone()
        total = int(analysis_stats["total"] or 0)
        score_zero_count = int(analysis_stats["score_zero_count"] or 0)
        asn_missing_count = int(analysis_stats["asn_missing_count"] or 0)
        score_zero_ratio = (score_zero_count / total) if total else 0.0
        asn_missing_ratio = (asn_missing_count / total) if total else 0.0
        ipinfo_token_present = bool(os.getenv("IPINFO_TOKEN"))

        degraded = not core_heartbeat["healthy"] or not ipinfo_token_present
        overall = "degraded" if degraded else "ok"
        return {
            "status": overall,
            "db": {"healthy": True, "path": self.db_path},
            "live_rules": {
                "revision": live_rules_state["revision"],
                "updated_at": live_rules_state["updated_at"],
                "updated_by": live_rules_state["updated_by"],
            },
            "core": core_heartbeat,
            "admin_sessions": admin_sessions,
            "ipinfo_token_present": ipinfo_token_present,
            "analysis_24h": {
                "total": total,
                "score_zero_count": score_zero_count,
                "score_zero_ratio": score_zero_ratio,
                "asn_missing_count": asn_missing_count,
                "asn_missing_ratio": asn_missing_ratio,
            },
        }

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
