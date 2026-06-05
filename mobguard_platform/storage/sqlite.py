from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar


T = TypeVar("T")


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


def is_sqlite_interrupted_error(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    return "interrupted" in str(exc).lower()


def run_with_sqlite_retry(
    operation: Callable[[], T],
    *,
    retry_delays_seconds: tuple[float, ...] = (),
    retry_on_interrupted: bool = False,
) -> T:
    attempts = max(len(retry_delays_seconds), 0) + 1
    for attempt in range(attempts):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            busy = is_sqlite_busy_error(exc)
            interrupted = retry_on_interrupted and is_sqlite_interrupted_error(exc)
            if not (busy or interrupted) or attempt >= len(retry_delays_seconds):
                raise
            delay = max(float(retry_delays_seconds[attempt]), 0.0)
            if delay > 0:
                time.sleep(delay)
    return operation()


@dataclass
class SQLiteStorage:
    db_path: str
    timeout: int = 30
    busy_timeout_ms: int = 30000
    backend: str = "sqlite"

    def connect(
        self,
        *,
        timeout: Optional[float] = None,
        busy_timeout_ms: Optional[int] = None,
        query_time_limit_ms: Optional[int] = None,
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
        if query_time_limit_ms is not None and int(query_time_limit_ms) > 0:
            deadline = time.monotonic() + (int(query_time_limit_ms) / 1000.0)

            def _progress_handler() -> int:
                return 1 if time.monotonic() >= deadline else 0

            conn.set_progress_handler(_progress_handler, 1000)
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
