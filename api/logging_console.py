from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from mobguard_platform.storage.config import DatabaseBackendConfig


ALLOWED_LOGGER_PREFIXES = (
    "api",
    "mobguard",
    "mobguard_platform",
    "uvicorn.error",
)
BLOCKED_LOGGER_PREFIXES = (
    "uvicorn.access",
    "watchfiles",
)


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


class _BaseConsoleLogHandler(logging.Handler):
    def __init__(self, *, service_name: str = "mobguard-api") -> None:
        super().__init__(level=logging.INFO)
        self.service_name = str(service_name or "mobguard-api").strip() or "mobguard-api"
        self._mobguard_console_handler = True

    def _should_skip(self, record: logging.LogRecord) -> bool:
        logger_name = str(record.name or "")
        if BLOCKED_LOGGER_PREFIXES and logger_name.startswith(BLOCKED_LOGGER_PREFIXES):
            return True
        if ALLOWED_LOGGER_PREFIXES and not logger_name.startswith(ALLOWED_LOGGER_PREFIXES):
            return True
        return False

    def _details(self, record: logging.LogRecord) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "pathname": str(getattr(record, "pathname", "") or ""),
            "lineno": int(getattr(record, "lineno", 0) or 0),
            "module": str(getattr(record, "module", "") or ""),
            "funcName": str(getattr(record, "funcName", "") or ""),
        }
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info)).strip()
        return payload



class PostgresConsoleLogHandler(_BaseConsoleLogHandler):
    def __init__(self, dsn: str, *, service_name: str = "mobguard-api") -> None:
        super().__init__(service_name=service_name)
        self.dsn = str(dsn or "").strip()

    def emit(self, record: logging.LogRecord) -> None:
        if self._should_skip(record):
            return
        try:
            import psycopg

            with psycopg.connect(self.dsn, connect_timeout=1) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO system_console_events (
                            service_name, logger_name, level, message, details_json, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            self.service_name,
                            str(record.name or ""),
                            str(record.levelname or "INFO").upper(),
                            record.getMessage(),
                            json.dumps(self._details(record), ensure_ascii=False),
                            _utcnow(),
                        ),
                    )
                conn.commit()
        except Exception:
            return


def ensure_console_logging(
    database: DatabaseBackendConfig,
    db_path: str | Path,
    *,
    service_name: str = "mobguard-api",
) -> None:
    root_logger = logging.getLogger()
    handler_key = database.resolve_postgres_dsn() if database.backend == "postgres" else str(db_path)
    for handler in root_logger.handlers:
        if (
            getattr(handler, "_mobguard_console_handler", False)
            and getattr(handler, "service_name", None) == service_name
            and (
                getattr(handler, "db_path", None) == handler_key
                or getattr(handler, "dsn", None) == handler_key
            )
        ):
            return
    if database.backend == "postgres":
        dsn = database.resolve_postgres_dsn()
        if not dsn:
            return
        root_logger.addHandler(PostgresConsoleLogHandler(dsn, service_name=service_name))
    for logger_name in ("api", "mobguard", "mobguard_platform"):
        current_logger = logging.getLogger(logger_name)
        if current_logger.level in {logging.NOTSET, 0} or current_logger.level > logging.INFO:
            current_logger.setLevel(logging.INFO)
