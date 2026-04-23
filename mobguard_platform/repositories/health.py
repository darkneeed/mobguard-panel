from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Callable

from .base import SQLiteRepository


def utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


class ServiceHealthRepository(SQLiteRepository):
    def __init__(self, storage, db_path: str):
        super().__init__(storage)
        self.db_path = db_path

    def update_heartbeat(
        self,
        service_name: str,
        status: str = "ok",
        details: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
        busy_timeout_ms: int | None = None,
    ) -> None:
        now = utcnow()
        with self.storage.connect(timeout=timeout, busy_timeout_ms=busy_timeout_ms) as conn:
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

    def get_heartbeat(self, service_name: str, stale_after_seconds: int = 60) -> dict[str, Any]:
        with self.storage.connect() as conn:
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

    def get_snapshot(
        self,
        *,
        live_rules_state_loader: Callable[[], dict[str, Any]],
        core_service_name: str = "mobguard-core",
        timeout: float | None = None,
        busy_timeout_ms: int | None = None,
        query_time_limit_ms: int | None = None,
    ) -> dict[str, Any]:
        live_rules_state = live_rules_state_loader()
        with self.storage.connect(
            timeout=timeout,
            busy_timeout_ms=busy_timeout_ms,
            query_time_limit_ms=query_time_limit_ms,
        ) as conn:
            row = conn.execute(
                "SELECT service_name, status, details_json, updated_at FROM service_heartbeats WHERE service_name = ?",
                (core_service_name,),
            ).fetchone()
            if not row:
                core_heartbeat = {"service_name": core_service_name, "healthy": False, "status": "missing", "updated_at": ""}
            else:
                updated_at = datetime.fromisoformat(row["updated_at"])
                age = (datetime.utcnow() - updated_at).total_seconds()
                core_heartbeat = {
                    "service_name": row["service_name"],
                    "healthy": age <= 60 and row["status"] == "ok",
                    "status": row["status"],
                    "updated_at": row["updated_at"],
                    "age_seconds": int(age),
                    "details": json.loads(row["details_json"]),
                }
            conn.execute("SELECT 1").fetchone()
            admin_sessions = conn.execute(
                "SELECT COUNT(*) AS cnt FROM admin_sessions WHERE expires_at > ?",
                (utcnow(),),
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
        if core_heartbeat["status"] == "missing":
            core_snapshot = {
                "service_name": core_service_name,
                "healthy": True,
                "status": "embedded",
                "mode": "embedded",
                "updated_at": utcnow(),
                "age_seconds": 0,
                "details": {
                    "runtime": "mobguard-api",
                    "note": "scoring runtime is embedded in the panel API process",
                },
            }
        else:
            core_snapshot = {**core_heartbeat, "mode": "heartbeat"}
        total = int(analysis_stats["total"] or 0)
        score_zero_count = int(analysis_stats["score_zero_count"] or 0)
        asn_missing_count = int(analysis_stats["asn_missing_count"] or 0)
        score_zero_ratio = (score_zero_count / total) if total else 0.0
        asn_missing_ratio = (asn_missing_count / total) if total else 0.0
        ipinfo_token_present = bool(os.getenv("IPINFO_TOKEN"))
        degraded = not core_snapshot["healthy"] or not ipinfo_token_present
        overall = "degraded" if degraded else "ok"
        return {
            "status": overall,
            "db": {"healthy": True, "path": self.db_path},
            "live_rules": {
                "revision": live_rules_state["revision"],
                "updated_at": live_rules_state["updated_at"],
                "updated_by": live_rules_state["updated_by"],
            },
            "core": core_snapshot,
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
