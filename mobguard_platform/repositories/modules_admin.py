from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Optional

from .base import SQLiteRepository


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


class ModuleAdminRepository(SQLiteRepository):
    def get_module(self, module_id: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
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
        with self.connect() as conn:
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
        with self.connect() as conn:
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
                (normalized_name, metadata_json, normalized_id),
            )
            conn.commit()
        module = self.get_module(normalized_id)
        if not module:
            raise ValueError("Module is not registered")
        return module

    def get_module_token_ciphertext(self, module_id: str) -> str:
        normalized_id = str(module_id or "").strip()
        with self.connect() as conn:
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
        with self.connect() as conn:
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
        with self.connect() as conn:
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
        with self.connect() as conn:
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
        with self.connect() as conn:
            rows = conn.execute(
                """
                WITH open_case_counts AS (
                    SELECT rcm.module_id, COUNT(DISTINCT rcm.case_id) AS open_review_cases
                    FROM review_case_modules rcm
                    JOIN review_cases rc ON rc.id = rcm.case_id
                    WHERE rc.status = 'OPEN'
                    GROUP BY rcm.module_id
                ),
                analysis_counts AS (
                    SELECT ae.module_id, COUNT(*) AS analysis_events_count
                    FROM analysis_events ae
                    GROUP BY ae.module_id
                )
                SELECT m.module_id, m.module_name, m.status, m.version, m.protocol_version,
                       m.config_revision_applied, m.first_seen_at, m.last_seen_at, m.install_state,
                       m.managed, m.health_status, m.error_text, m.last_validation_at,
                       m.spool_depth, m.access_log_exists, m.metadata_json,
                       COALESCE(occ.open_review_cases, 0) AS open_review_cases,
                       COALESCE(ac.analysis_events_count, 0) AS analysis_events_count
                FROM modules m
                LEFT JOIN open_case_counts occ ON occ.module_id = m.module_id
                LEFT JOIN analysis_counts ac ON ac.module_id = m.module_id
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
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO ingested_raw_events (
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
            if cursor.rowcount is not None:
                return int(cursor.rowcount) > 0
            row = conn.execute("SELECT changes() AS cnt").fetchone()
            return bool(row and int(row["cnt"]) > 0)

    def mark_raw_event_processed(
        self,
        event_uid: str,
        *,
        analysis_event_id: Optional[int] = None,
        review_case_id: Optional[int] = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE ingested_raw_events
                SET processed_at = ?, analysis_event_id = ?, review_case_id = ?
                WHERE event_uid = ?
                """,
                (_utcnow(), analysis_event_id, review_case_id, event_uid),
            )
            conn.commit()
