from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

from .storage.sqlite import SQLiteStorage


def utcnow() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def utcnow_iso() -> str:
    return utcnow().isoformat()


class AnalysisStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.storage = SQLiteStorage(db_path)

    def _connect(self) -> sqlite3.Connection:
        return self.storage.connect()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS violations (
                    uuid TEXT PRIMARY KEY,
                    strikes INTEGER,
                    unban_time TEXT,
                    last_forgiven TEXT,
                    last_strike_time TEXT,
                    warning_time TEXT,
                    warning_count INTEGER DEFAULT 0,
                    restriction_mode TEXT DEFAULT 'SQUAD',
                    saved_traffic_limit_bytes INTEGER,
                    saved_traffic_limit_strategy TEXT,
                    applied_traffic_limit_bytes INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS violation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT,
                    ip TEXT,
                    isp TEXT,
                    asn INTEGER,
                    tag TEXT,
                    strike_number INTEGER,
                    punishment_duration INTEGER,
                    timestamp TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS manual_traffic_cap_overrides (
                    uuid TEXT PRIMARY KEY,
                    saved_traffic_limit_bytes INTEGER,
                    saved_traffic_limit_strategy TEXT,
                    applied_traffic_limit_bytes INTEGER,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS active_trackers (
                    key TEXT PRIMARY KEY,
                    start_time TEXT,
                    last_seen TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ip_decisions (
                    ip TEXT PRIMARY KEY,
                    status TEXT,
                    confidence TEXT,
                    details TEXT,
                    asn INTEGER,
                    expires TEXT,
                    log_json TEXT,
                    bundle_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unsure_patterns (
                    ip_pattern TEXT PRIMARY KEY,
                    decision TEXT,
                    timestamp TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subnet_evidence (
                    subnet TEXT PRIMARY KEY,
                    mobile_count INTEGER DEFAULT 0,
                    home_count INTEGER DEFAULT 0,
                    last_updated TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ip_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT,
                    ip TEXT,
                    timestamp TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_type TEXT NOT NULL,
                    stat_key TEXT NOT NULL,
                    sub_key TEXT NOT NULL DEFAULT '',
                    value INTEGER NOT NULL DEFAULT 0,
                    date TEXT NOT NULL,
                    UNIQUE(stat_type, stat_key, sub_key, date)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trackers_last_seen ON active_trackers(last_seen)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_expires ON ip_decisions(expires)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_history_uuid ON ip_history(uuid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_history_uuid_timestamp ON ip_history(uuid, timestamp)")
            conn.commit()

    async def _run(self, fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn, *args)

    def _fetch_one(self, query: str, args: tuple[Any, ...]) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(query, args).fetchone()

    def _fetch_all(self, query: str, args: tuple[Any, ...]) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(conn.execute(query, args).fetchall())

    def _execute(self, query: str, args: tuple[Any, ...]) -> None:
        with self._connect() as conn:
            conn.execute(query, args)
            conn.commit()

    async def fetch_one(self, query: str, args: tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
        return await self._run(self._fetch_one, query, args)

    async def fetch_all(self, query: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return await self._run(self._fetch_all, query, args)

    async def execute(self, query: str, args: tuple[Any, ...] = ()) -> None:
        await self._run(self._execute, query, args)

    def get_subnet(self, ip: str) -> str:
        return ip.rsplit(".", 1)[0]

    async def get_cached_decision(self, ip: str) -> Optional[dict[str, Any]]:
        row = await self.fetch_one(
            """
            SELECT status, confidence, details, asn, expires, log_json, bundle_json
            FROM ip_decisions
            WHERE ip = ?
            """,
            (ip,),
        )
        if not row:
            return None
        expires_at = row["expires"]
        if expires_at and datetime.fromisoformat(str(expires_at)) <= utcnow():
            return None
        return {
            "status": row["status"],
            "confidence": row["confidence"],
            "isp": row["details"],
            "asn": row["asn"],
            "log": json.loads(row["log_json"] or "[]"),
            "bundle": json.loads(row["bundle_json"]) if row["bundle_json"] else None,
        }

    async def cache_decision(self, ip: str, data: dict[str, Any]) -> None:
        expires = utcnow() + timedelta(days=3)
        await self.execute(
            """
            INSERT OR REPLACE INTO ip_decisions (ip, status, confidence, details, asn, expires, log_json, bundle_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ip,
                data["status"],
                data["confidence"],
                data["details"],
                data.get("asn"),
                expires.isoformat(),
                json.dumps(data.get("log", []), ensure_ascii=False),
                json.dumps(data.get("bundle"), ensure_ascii=False) if data.get("bundle") else None,
            ),
        )

    async def get_unsure_pattern(self, ip: str) -> Optional[str]:
        row = await self.fetch_one("SELECT decision FROM unsure_patterns WHERE ip_pattern = ?", (ip,))
        return str(row["decision"]) if row else None

    async def set_unsure_pattern(self, ip: str, decision: str) -> None:
        now = utcnow_iso()
        await self.execute(
            """
            INSERT OR REPLACE INTO unsure_patterns (ip_pattern, decision, timestamp)
            VALUES (?, ?, ?)
            """,
            (ip, decision, now),
        )

    async def invalidate_ip_cache(self, ip: str) -> None:
        await self.execute("DELETE FROM ip_decisions WHERE ip = ?", (ip,))

    async def get_learning_confidence(self, pattern_type: str, pattern_value: str, decision: str) -> int:
        row = await self.fetch_one(
            """
            SELECT confidence
            FROM unsure_learning
            WHERE pattern_type = ? AND pattern_value = ? AND decision = ?
            """,
            (pattern_type, pattern_value, decision),
        )
        return int(row["confidence"]) if row else 0

    async def count_concurrent_users(self, ip: str, minutes: int = 15) -> int:
        cutoff = (utcnow() - timedelta(minutes=minutes)).isoformat()
        row = await self.fetch_one(
            """
            SELECT COUNT(DISTINCT SUBSTR(key, 1, INSTR(key, ':') - 1)) AS cnt
            FROM active_trackers
            WHERE key LIKE ? AND last_seen > ?
            """,
            (f"%:{ip}", cutoff),
        )
        return int(row["cnt"]) if row else 0

    async def get_churn_rate(self, uuid: str, hours: int) -> int:
        cutoff = (utcnow() - timedelta(hours=hours)).isoformat()
        row = await self.fetch_one(
            "SELECT COUNT(DISTINCT ip) AS cnt FROM ip_history WHERE uuid = ? AND timestamp > ?",
            (uuid, cutoff),
        )
        return int(row["cnt"]) if row else 0

    async def get_recent_ip_history(
        self,
        uuid: str,
        days: int,
        *,
        limit: int = 1000,
    ) -> list[dict[str, str]]:
        cutoff = (utcnow() - timedelta(days=max(days, 1))).isoformat()
        rows = await self.fetch_all(
            """
            SELECT ip, timestamp
            FROM ip_history
            WHERE uuid = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (uuid, cutoff, max(int(limit), 1)),
        )
        return [
            {
                "ip": str(row["ip"] or "").strip(),
                "timestamp": str(row["timestamp"] or "").strip(),
            }
            for row in rows
            if str(row["ip"] or "").strip() and str(row["timestamp"] or "").strip()
        ]

    async def get_session_lifetime(self, uuid: str, ip: str) -> float:
        row = await self.fetch_one(
            "SELECT start_time, last_seen FROM active_trackers WHERE key = ?",
            (f"{uuid}:{ip}",),
        )
        if not row:
            return 0.0
        start_time = datetime.fromisoformat(str(row["start_time"]))
        last_seen = datetime.fromisoformat(str(row["last_seen"]))
        return (last_seen - start_time).total_seconds() / 3600.0

    async def record_subnet_signal(self, ip: str, uuid: str, signal: str) -> None:
        subnet = self.get_subnet(ip)
        now = utcnow_iso()
        mobile = 1 if signal == "MOBILE" else 0
        home = 1 if signal == "HOME" else 0
        await self.execute(
            """
            INSERT INTO subnet_evidence (subnet, mobile_count, home_count, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(subnet) DO UPDATE SET
                mobile_count = mobile_count + ?,
                home_count = home_count + ?,
                last_updated = excluded.last_updated
            """,
            (subnet, mobile, home, now, mobile, home),
        )

    async def get_subnet_evidence(self, ip: str) -> dict[str, int]:
        row = await self.fetch_one(
            "SELECT mobile_count, home_count FROM subnet_evidence WHERE subnet = ?",
            (self.get_subnet(ip),),
        )
        if not row:
            return {"MOBILE": 0, "HOME": 0}
        return {"MOBILE": int(row["mobile_count"]), "HOME": int(row["home_count"])}

    async def update_ip_history(self, uuid: str, ip: str) -> None:
        await self.execute(
            "INSERT INTO ip_history (uuid, ip, timestamp) VALUES (?, ?, ?)",
            (uuid, ip, utcnow_iso()),
        )

    async def update_session(self, uuid: str, ip: str, tag: str) -> None:
        key = f"{uuid}:{ip}"
        now = utcnow_iso()
        await self.execute(
            """
            INSERT INTO active_trackers (key, start_time, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (key, now, now),
        )

    async def delete_tracker(self, key: str) -> None:
        await self.execute("DELETE FROM active_trackers WHERE key = ?", (key,))

    async def clear_trackers_for_uuid(self, uuid: str) -> int:
        rows = await self.fetch_all("SELECT key FROM active_trackers WHERE key LIKE ?", (f"{uuid}:%",))
        if rows:
            await self.execute("DELETE FROM active_trackers WHERE key LIKE ?", (f"{uuid}:%",))
        return len(rows)
