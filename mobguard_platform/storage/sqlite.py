from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass
class SQLiteStorage:
    db_path: str
    timeout: int = 30
    busy_timeout_ms: int = 5000

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
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
