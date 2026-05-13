from __future__ import annotations

import argparse
import os
import re
import sqlite3
from pathlib import Path
from typing import Iterable


DDL_AUTOINCREMENT_RE = re.compile(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", re.IGNORECASE)
DDL_INTEGER_RE = re.compile(r"\bINTEGER\b", re.IGNORECASE)
DDL_REAL_RE = re.compile(r"\bREAL\b", re.IGNORECASE)
DDL_BLOB_RE = re.compile(r"\bBLOB\b", re.IGNORECASE)
DDL_AUTOINCREMENT_TOKEN_RE = re.compile(r"\bAUTOINCREMENT\b", re.IGNORECASE)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate MobGuard operational data from SQLite to Postgres")
    parser.add_argument("--sqlite-path", default=os.getenv("MOBGUARD_SQLITE_PATH", ""), help="Path to SQLite DB file")
    parser.add_argument(
        "--postgres-dsn",
        default=os.getenv("MOBGUARD_POSTGRES_DSN", ""),
        help="Postgres DSN, for example postgresql://user:pass@host:5432/dbname",
    )
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Do not truncate existing target tables before loading data",
    )
    return parser.parse_args()


def _connect_postgres(dsn: str):
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("psycopg is required for Postgres migration. Install requirements-api.txt first.") from exc
    return psycopg.connect(dsn)


def _validate_postgres_dsn(dsn: str) -> str:
    normalized = str(dsn or "").strip()
    if not normalized:
        raise SystemExit("Missing --postgres-dsn or MOBGUARD_POSTGRES_DSN")
    if normalized in {"...", "<dsn>", "<postgres-dsn>"}:
        raise SystemExit(
            "Invalid Postgres DSN placeholder. Pass a real DSN, for example: "
            "postgresql://mobguard:secret@postgres:5432/mobguard"
        )
    if "://" not in normalized and "=" not in normalized:
        raise SystemExit(
            "Invalid Postgres DSN format. Expected URI form like "
            "postgresql://user:pass@host:5432/dbname or libpq form like "
            "'host=... port=5432 dbname=... user=... password=...'."
        )
    return normalized


def _sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name ASC
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def _sqlite_indexes(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'index'
          AND sql IS NOT NULL
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name ASC
        """
    ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


def _table_ddl(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not row or not row[0]:
        raise ValueError(f"Missing CREATE TABLE statement for {table_name}")
    return _normalize_postgres_ddl(str(row[0]))


def _normalize_postgres_ddl(ddl: str) -> str:
    normalized = DDL_AUTOINCREMENT_RE.sub("BIGSERIAL PRIMARY KEY", ddl)
    normalized = DDL_AUTOINCREMENT_TOKEN_RE.sub("", normalized)
    normalized = DDL_INTEGER_RE.sub("BIGINT", normalized)
    normalized = DDL_REAL_RE.sub("DOUBLE PRECISION", normalized)
    normalized = DDL_BLOB_RE.sub("BYTEA", normalized)
    return normalized.strip()


def _quoted(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({_quoted(table_name)})").fetchall()
    return [str(row[1]) for row in rows]


def _table_pk_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({_quoted(table_name)})").fetchall()
    return [str(row[1]) for row in rows if int(row[5] or 0) > 0]


def _table_rows(conn: sqlite3.Connection, table_name: str) -> Iterable[tuple]:
    cursor = conn.execute(f"SELECT * FROM {_quoted(table_name)}")
    for row in cursor:
        yield tuple(row)


def _ensure_schema(sqlite_conn: sqlite3.Connection, pg_conn) -> None:
    with pg_conn.cursor() as cursor:
        for table_name in _sqlite_tables(sqlite_conn):
            cursor.execute(_table_ddl(sqlite_conn, table_name))
        for _, index_ddl in _sqlite_indexes(sqlite_conn):
            cursor.execute(index_ddl)
    pg_conn.commit()


def _truncate_table(pg_conn, table_name: str) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {_quoted(table_name)} RESTART IDENTITY CASCADE")
    pg_conn.commit()


def _copy_table(sqlite_conn: sqlite3.Connection, pg_conn, table_name: str) -> int:
    columns = _table_columns(sqlite_conn, table_name)
    if not columns:
        return 0
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(_quoted(column) for column in columns)
    insert_sql = f"INSERT INTO {_quoted(table_name)} ({column_sql}) VALUES ({placeholders})"
    copied = 0
    with pg_conn.cursor() as cursor:
        for row in _table_rows(sqlite_conn, table_name):
            cursor.execute(insert_sql, row)
            copied += 1
    pg_conn.commit()
    _sync_sequence(pg_conn, table_name, _table_pk_columns(sqlite_conn, table_name))
    return copied


def _sync_sequence(pg_conn, table_name: str, pk_columns: list[str]) -> None:
    if len(pk_columns) != 1:
        return
    pk_column = pk_columns[0]
    with pg_conn.cursor() as cursor:
        cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", (table_name, pk_column))
        sequence_row = cursor.fetchone()
        if not sequence_row or not sequence_row[0]:
            pg_conn.commit()
            return
        cursor.execute(
            f"SELECT COALESCE(MAX({_quoted(pk_column)}), 0) FROM {_quoted(table_name)}"
        )
        max_row = cursor.fetchone()
        max_value = int(max_row[0] or 0) if max_row else 0
        cursor.execute("SELECT setval(%s, %s, %s)", (sequence_row[0], max_value, max_value > 0))
    pg_conn.commit()


def _validate_counts(sqlite_conn: sqlite3.Connection, pg_conn, table_names: list[str]) -> None:
    for table_name in table_names:
        sqlite_count = int(sqlite_conn.execute(f"SELECT COUNT(*) FROM {_quoted(table_name)}").fetchone()[0] or 0)
        with pg_conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {_quoted(table_name)}")
            pg_count = int(cursor.fetchone()[0] or 0)
        if sqlite_count != pg_count:
            raise SystemExit(
                f"Count mismatch after migration for {table_name}: sqlite={sqlite_count} postgres={pg_count}"
            )


def main() -> int:
    args = _parse_args()
    sqlite_path = str(args.sqlite_path or "").strip()
    postgres_dsn = _validate_postgres_dsn(args.postgres_dsn)
    if not sqlite_path:
        raise SystemExit("Missing --sqlite-path or MOBGUARD_SQLITE_PATH")
    if not Path(sqlite_path).exists():
        raise SystemExit(f"SQLite DB not found: {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    try:
        postgres_conn = _connect_postgres(postgres_dsn)
        try:
            table_names = _sqlite_tables(sqlite_conn)
            _ensure_schema(sqlite_conn, postgres_conn)
            for table_name in table_names:
                if not args.preserve_existing:
                    _truncate_table(postgres_conn, table_name)
                copied = _copy_table(sqlite_conn, postgres_conn, table_name)
                print(f"{table_name}: copied {copied} row(s)")
            _validate_counts(sqlite_conn, postgres_conn, table_names)
            print(f"Validated {len(table_names)} table count(s)")
        finally:
            postgres_conn.close()
    finally:
        sqlite_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
