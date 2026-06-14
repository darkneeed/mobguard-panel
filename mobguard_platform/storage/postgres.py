from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


_NOW_TEXT_SQL = """to_char((CURRENT_TIMESTAMP AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS')"""
_INSERT_OR_IGNORE_RE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", re.IGNORECASE)
_INSERT_OR_REPLACE_RE = re.compile(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+", re.IGNORECASE)
_INSERT_TABLE_RE = re.compile(r"^\s*INSERT\s+(?:OR\s+(?:IGNORE|REPLACE)\s+)?INTO\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_INSERT_COLUMNS_RE = re.compile(
    r"^\s*INSERT\s+(?:OR\s+(?:IGNORE|REPLACE)\s+)?INTO\s+[A-Za-z_][A-Za-z0-9_]*\s*\((.*?)\)\s*VALUES",
    re.IGNORECASE | re.DOTALL,
)
_PRAGMA_TABLE_INFO_RE = re.compile(r"^\s*PRAGMA\s+table_info\(([^)]+)\)\s*$", re.IGNORECASE)
_PRAGMA_INDEX_LIST_RE = re.compile(r"^\s*PRAGMA\s+index_list\(([^)]+)\)\s*$", re.IGNORECASE)
_PRAGMA_BUSY_TIMEOUT_RE = re.compile(r"^\s*PRAGMA\s+busy_timeout\s*=", re.IGNORECASE)
_PRAGMA_JOURNAL_MODE_RE = re.compile(r"^\s*PRAGMA\s+journal_mode(?:\s*=\s*WAL)?\s*$", re.IGNORECASE)
_PRAGMA_WAL_CHECKPOINT_RE = re.compile(r"^\s*PRAGMA\s+wal_checkpoint(?:\(([^)]*)\))?\s*$", re.IGNORECASE)
_SQLITE_MASTER_TABLE_RE = re.compile(
    r"^\s*SELECT\s+1\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*'table'\s+AND\s+name\s*=\s*(?:\?|'.*?')\s*$",
    re.IGNORECASE,
)
_SELECT_CHANGES_RE = re.compile(r"^\s*SELECT\s+changes\(\)\s+AS\s+cnt\s*$", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\bRETURNING\b", re.IGNORECASE)


class CompatRow:
    def __init__(self, columns: Sequence[str], values: Sequence[Any]):
        self._columns = list(columns)
        self._values = list(values)
        self._mapping = {column: self._values[index] for index, column in enumerate(self._columns)}

    def __getitem__(self, key: int | str):
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def keys(self):
        return list(self._columns)

    def items(self):
        return self._mapping.items()

    def values(self):
        return list(self._values)

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping.get(key, default)

    def __contains__(self, key: object) -> bool:
        return key in self._mapping

    def __repr__(self) -> str:
        return f"CompatRow({self._mapping!r})"


class CompatCursor:
    def __init__(
        self,
        *,
        columns: Sequence[str] = (),
        rows: Sequence[Sequence[Any]] = (),
        rowcount: int = -1,
        lastrowid: int | None = None,
    ):
        self._columns = list(columns)
        self._rows = [CompatRow(self._columns, row) for row in rows]
        self._offset = 0
        self.rowcount = int(rowcount)
        self.lastrowid = lastrowid

    def fetchone(self):
        if self._offset >= len(self._rows):
            return None
        row = self._rows[self._offset]
        self._offset += 1
        return row

    def fetchall(self):
        if self._offset >= len(self._rows):
            return []
        rows = self._rows[self._offset :]
        self._offset = len(self._rows)
        return rows


class PostgresCompatConnection:
    def __init__(self, storage: "PostgresStorage", raw_connection):
        self.storage = storage
        self._conn = raw_connection
        self._last_changes = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

    def close(self) -> None:
        self._conn.close()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def set_progress_handler(self, handler, n: int) -> None:
        return None

    def execute(self, query: str, args: Sequence[Any] = ()):
        try:
            handled = self.storage.handle_special_query(self, query, tuple(args))
            if handled is not None:
                return handled
            sql, params, table_name = self.storage.translate_query(self, query, tuple(args))
            with self._conn.cursor() as cursor:
                cursor.execute(sql, params)
                columns = [item.name for item in cursor.description] if cursor.description else []
                rows = cursor.fetchall() if cursor.description else []
                rowcount = int(cursor.rowcount or 0) if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
            if table_name and sql.lstrip().upper().startswith("INSERT"):
                self._last_changes = rowcount
            elif sql.lstrip().upper().startswith(("UPDATE", "DELETE")):
                self._last_changes = rowcount
            lastrowid = None
            if rows and columns and "id" in columns:
                first = CompatRow(columns, rows[0])
                raw_id = first.get("id")
                if raw_id is not None:
                    try:
                        lastrowid = int(raw_id)
                    except (TypeError, ValueError):
                        lastrowid = None
            return CompatCursor(columns=columns, rows=rows, rowcount=rowcount, lastrowid=lastrowid)
        except Exception as exc:  # pragma: no cover - translated below
            raise self.storage.translate_exception(exc) from None


@dataclass
class PostgresStorage:
    dsn: str
    timeout: int = 30
    busy_timeout_ms: int = 30000
    backend: str = "postgres"

    def __post_init__(self):
        self._primary_key_cache: dict[str, list[str]] = {}
        self._column_cache: dict[str, list[str]] = {}

    def connect(
        self,
        *,
        timeout: float | None = None,
        busy_timeout_ms: int | None = None,
        query_time_limit_ms: int | None = None,
    ) -> PostgresCompatConnection:
        psycopg = self._psycopg()
        connect_timeout = max(int(timeout if timeout is not None else self.timeout), 1)
        options: list[str] = []
        if query_time_limit_ms is not None and int(query_time_limit_ms) > 0:
            options.append(f"-c statement_timeout={int(query_time_limit_ms)}")
        raw = psycopg.connect(
            self.dsn,
            connect_timeout=connect_timeout,
            options=" ".join(options) if options else None,
        )
        return PostgresCompatConnection(self, raw)

    def table_exists(self, conn: PostgresCompatConnection, table_name: str) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = ?
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    def handle_special_query(
        self,
        conn: PostgresCompatConnection,
        query: str,
        args: tuple[Any, ...],
    ) -> CompatCursor | None:
        normalized = str(query or "").strip()
        if not normalized:
            return CompatCursor()
        if _PRAGMA_BUSY_TIMEOUT_RE.match(normalized):
            return CompatCursor()
        if _PRAGMA_JOURNAL_MODE_RE.match(normalized):
            return CompatCursor(columns=("journal_mode",), rows=(("wal",),), rowcount=1)
        checkpoint_match = _PRAGMA_WAL_CHECKPOINT_RE.match(normalized)
        if checkpoint_match:
            return CompatCursor(columns=("busy", "log", "checkpointed"), rows=((0, 0, 0),), rowcount=1)
        table_info_match = _PRAGMA_TABLE_INFO_RE.match(normalized)
        if table_info_match:
            table_name = self._normalize_identifier(table_info_match.group(1))
            rows = self._table_info_rows(conn, table_name)
            return CompatCursor(
                columns=("cid", "name", "type", "notnull", "dflt_value", "pk"),
                rows=rows,
                rowcount=len(rows),
            )
        index_list_match = _PRAGMA_INDEX_LIST_RE.match(normalized)
        if index_list_match:
            table_name = self._normalize_identifier(index_list_match.group(1))
            rows = self._index_list_rows(conn, table_name)
            return CompatCursor(columns=("seq", "name", "unique", "origin", "partial"), rows=rows, rowcount=len(rows))
        if _SQLITE_MASTER_TABLE_RE.match(normalized):
            table_name = str(args[0]) if args else self._extract_literal_table_name(normalized)
            rows = self._run_internal_query(
                conn,
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = %s
                """,
                (table_name,),
            )
            return CompatCursor(columns=("1",), rows=rows, rowcount=len(rows))
        if _SELECT_CHANGES_RE.match(normalized):
            return CompatCursor(columns=("cnt",), rows=((conn._last_changes,),), rowcount=1)
        if normalized.upper() == "BEGIN IMMEDIATE":
            return CompatCursor()
        return None

    def translate_query(
        self,
        conn: PostgresCompatConnection,
        query: str,
        args: tuple[Any, ...],
    ) -> tuple[str, tuple[Any, ...], str | None]:
        translated = self._replace_datetime_now(str(query or ""))
        translated = re.sub(r"\bINSTR\s*\(", "STRPOS(", translated, flags=re.IGNORECASE)
        translated = translated.replace("INSERT OR IGNORE INTO", "INSERT OR IGNORE INTO")
        table_name = self._extract_insert_table_name(translated)
        if _INSERT_OR_IGNORE_RE.match(translated):
            translated = _INSERT_OR_IGNORE_RE.sub("INSERT INTO ", translated, count=1)
            translated = f"{translated} ON CONFLICT DO NOTHING"
        elif _INSERT_OR_REPLACE_RE.match(translated):
            translated = self._rewrite_insert_or_replace(conn, translated)
            table_name = self._extract_insert_table_name(translated)
        translated = self._replace_placeholders(translated)
        if table_name and translated.lstrip().upper().startswith("INSERT") and not _RETURNING_RE.search(translated):
            pk_columns = self._primary_key_columns(conn, table_name)
            if pk_columns == ["id"]:
                translated = f"{translated} RETURNING id"
        return translated, args, table_name

    def translate_exception(self, exc: BaseException) -> sqlite3.OperationalError:
        if isinstance(exc, sqlite3.Error):
            return exc if isinstance(exc, sqlite3.OperationalError) else sqlite3.OperationalError(str(exc))
        psycopg = self._psycopg()
        query_canceled = getattr(psycopg.errors, "QueryCanceled", None)
        if query_canceled and isinstance(exc, query_canceled):
            return sqlite3.OperationalError("interrupted")
        operational_error = getattr(psycopg, "OperationalError", None)
        if operational_error and isinstance(exc, operational_error):
            return sqlite3.OperationalError(str(exc))
        return sqlite3.OperationalError(str(exc))

    def _run_internal_query(self, conn: PostgresCompatConnection, query: str, args: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        with conn._conn.cursor() as cursor:
            cursor.execute(query, args)
            rows = cursor.fetchall()
        return [tuple(row) for row in rows]

    def _column_rows(self, conn: PostgresCompatConnection, table_name: str) -> list[tuple[Any, ...]]:
        return self._run_internal_query(
            conn,
            """
            SELECT column_name, data_type, is_nullable, column_default, ordinal_position
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            ORDER BY ordinal_position ASC
            """,
            (table_name,),
        )

    def _table_info_rows(self, conn: PostgresCompatConnection, table_name: str) -> list[tuple[Any, ...]]:
        columns = self._column_rows(conn, table_name)
        primary_keys = set(self._primary_key_columns(conn, table_name))
        rows: list[tuple[Any, ...]] = []
        for index, (column_name, data_type, is_nullable, column_default, _) in enumerate(columns):
            rows.append(
                (
                    index,
                    str(column_name),
                    str(data_type),
                    0 if str(is_nullable).upper() == "YES" else 1,
                    column_default,
                    1 if str(column_name) in primary_keys else 0,
                )
            )
        return rows

    def _index_list_rows(self, conn: PostgresCompatConnection, table_name: str) -> list[tuple[Any, ...]]:
        rows = self._run_internal_query(
            conn,
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = %s
            ORDER BY indexname ASC
            """,
            (table_name,),
        )
        payload: list[tuple[Any, ...]] = []
        for index, (index_name,) in enumerate(rows):
            payload.append((index, str(index_name), 0, "c", 0))
        return payload

    def _primary_key_columns(self, conn: PostgresCompatConnection, table_name: str) -> list[str]:
        cached = self._primary_key_cache.get(table_name)
        if cached is not None:
            return list(cached)
        rows = self._run_internal_query(
            conn,
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid
             AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass
              AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
            """,
            (table_name,),
        )
        payload = [str(row[0]) for row in rows]
        self._primary_key_cache[table_name] = payload
        return list(payload)

    def _rewrite_insert_or_replace(self, conn: PostgresCompatConnection, query: str) -> str:
        table_name = self._extract_insert_table_name(query)
        if not table_name:
            return query
        column_match = _INSERT_COLUMNS_RE.match(query)
        if not column_match:
            return query
        insert_columns = [self._normalize_identifier(item) for item in column_match.group(1).split(",")]
        pk_columns = self._primary_key_columns(conn, table_name)
        if not pk_columns:
            return query
        update_columns = [column for column in insert_columns if column not in pk_columns]
        if not update_columns:
            rewritten = _INSERT_OR_REPLACE_RE.sub("INSERT INTO ", query, count=1)
            return f"{rewritten} ON CONFLICT ({', '.join(pk_columns)}) DO NOTHING"
        assignments = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
        rewritten = _INSERT_OR_REPLACE_RE.sub("INSERT INTO ", query, count=1)
        return f"{rewritten} ON CONFLICT ({', '.join(pk_columns)}) DO UPDATE SET {assignments}"

    def _replace_datetime_now(self, query: str) -> str:
        return query.replace("datetime('now')", _NOW_TEXT_SQL)

    def _replace_placeholders(self, query: str) -> str:
        result: list[str] = []
        in_single = False
        in_double = False
        index = 0
        while index < len(query):
            char = query[index]
            if char == "'" and not in_double:
                if in_single and index + 1 < len(query) and query[index + 1] == "'":
                    result.append("''")
                    index += 2
                    continue
                in_single = not in_single
                result.append(char)
                index += 1
                continue
            if char == '"' and not in_single:
                in_double = not in_double
                result.append(char)
                index += 1
                continue
            if char == "%":
                result.append("%%")
                index += 1
                continue
            if char == "?" and not in_single and not in_double:
                result.append("%s")
                index += 1
                continue
            result.append(char)
            index += 1
        return "".join(result)

    def _extract_insert_table_name(self, query: str) -> str | None:
        match = _INSERT_TABLE_RE.match(query)
        if not match:
            return None
        return self._normalize_identifier(match.group(1))

    def _normalize_identifier(self, raw: str) -> str:
        return str(raw or "").strip().strip('"').strip("'")

    def _extract_literal_table_name(self, query: str) -> str:
        match = re.search(r"name\s*=\s*'([^']+)'", query, flags=re.IGNORECASE)
        return str(match.group(1)) if match else ""

    def _psycopg(self):
        import psycopg

        return psycopg
