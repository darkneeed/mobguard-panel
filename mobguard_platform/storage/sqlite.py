from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


def is_sqlite_busy_error(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "database is locked",
            "database table is locked",
            "database schema is locked",
        )
    )


@dataclass
class SQLiteStorage:
    db_path: str
    timeout: int = 30
    busy_timeout_ms: int = 30000

    def connect(
        self,
        *,
        timeout: Optional[float] = None,
        busy_timeout_ms: Optional[int] = None,
    ) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=self.timeout if timeout is None else timeout,
        )
        conn.row_factory = sqlite3.Row
        conn.execute(
            f"PRAGMA busy_timeout = {self.busy_timeout_ms if busy_timeout_ms is None else busy_timeout_ms}"
        )
        return conn

    def table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None


def sqlite_connect(db_path: str, timeout: Optional[int] = None) -> sqlite3.Connection:
    storage = SQLiteStorage(db_path=db_path, timeout=timeout or 30)
    return storage.connect()
