from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.services.runtime_state import panel_client
from mobguard_platform import AnalysisStore, PlatformStore, restore_remote_restriction_state
from mobguard_platform.runtime import load_runtime_context


TIMESTAMP_FIELDS = ("warning_time", "last_strike_time", "unban_time")


@dataclass
class IncidentWindow:
    start: str
    end: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset wrongly issued enforcement state for a bounded incident window."
    )
    parser.add_argument(
        "--from",
        dest="start",
        required=True,
        help="Inclusive incident start in ISO-8601, for example 2026-05-11T22:00:00",
    )
    parser.add_argument(
        "--to",
        dest="end",
        default=datetime.utcnow().replace(microsecond=0).isoformat(),
        help="Inclusive incident end in ISO-8601. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--runtime-dir",
        default=os.getenv("BAN_SYSTEM_DIR"),
        help="Optional runtime directory. Defaults to BAN_SYSTEM_DIR or repo runtime/.",
    )
    parser.add_argument(
        "--env-file",
        default=os.getenv("MOBGUARD_ENV_FILE"),
        help="Optional env file path. Needed for remote restore if the token is not in process env.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the reset. Without this flag the script only prints a preview.",
    )
    return parser.parse_args()


def _parse_iso8601(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("Timestamp is empty")
    return datetime.fromisoformat(normalized).replace(microsecond=0).isoformat()


def _load_container(runtime_dir: str | None, env_file: str | None) -> Any:
    if env_file:
        os.environ["MOBGUARD_ENV_FILE"] = env_file
    runtime = load_runtime_context(ROOT_DIR, runtime_dir)
    store = PlatformStore(runtime.db_path, runtime.config, str(runtime.config_path))
    analysis_store = AnalysisStore(runtime.db_path)
    analysis_store.init_schema()
    store.init_schema()
    store.sync_runtime_config(runtime.config)
    return SimpleNamespace(runtime=runtime, store=store, analysis_store=analysis_store)


def _current_violation_row(conn: sqlite3.Connection, uuid: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count,
               restriction_mode, saved_traffic_limit_bytes, saved_traffic_limit_strategy,
               applied_traffic_limit_bytes
        FROM violations
        WHERE uuid = ?
        """,
        (uuid,),
    ).fetchone()


def _ts_in_window(value: Any, window: IncidentWindow) -> bool:
    text = str(value or "").strip()
    return bool(text and window.start <= text <= window.end)


def _collect_affected_uuids(conn: sqlite3.Connection, window: IncidentWindow) -> list[str]:
    uuids: set[str] = set()
    rows = conn.execute(
        """
        SELECT uuid, warning_time, last_strike_time, unban_time
        FROM violations
        """
    ).fetchall()
    for row in rows:
        uuid = str(row["uuid"] or "").strip()
        if not uuid:
            continue
        if any(_ts_in_window(row[field], window) for field in TIMESTAMP_FIELDS):
            uuids.add(uuid)

    for table, ts_field, id_field in (
        ("violation_history", "timestamp", "uuid"),
        ("enforcement_jobs", "created_at", "subject_uuid"),
    ):
        query = f"""
            SELECT DISTINCT {id_field}
            FROM {table}
            WHERE {ts_field} >= ? AND {ts_field} <= ?
              AND {id_field} IS NOT NULL AND TRIM({id_field}) != ''
        """
        for row in conn.execute(query, (window.start, window.end)).fetchall():
            uuids.add(str(row[0]).strip())

    return sorted(uuid for uuid in uuids if uuid)


def _incident_history_rows(conn: sqlite3.Connection, uuid: str, window: IncidentWindow) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, strike_number, punishment_duration, timestamp
        FROM violation_history
        WHERE uuid = ? AND timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp ASC, id ASC
        """,
        (uuid, window.start, window.end),
    ).fetchall()


def _remaining_history_rows(conn: sqlite3.Connection, uuid: str, window: IncidentWindow) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, strike_number, punishment_duration, timestamp
        FROM violation_history
        WHERE uuid = ? AND (timestamp < ? OR timestamp > ?)
        ORDER BY timestamp ASC, id ASC
        """,
        (uuid, window.start, window.end),
    ).fetchall()


def _derive_restored_state(
    current: sqlite3.Row | None,
    incident_history: list[sqlite3.Row],
    remaining_history: list[sqlite3.Row],
    window: IncidentWindow,
) -> dict[str, Any]:
    current_payload = dict(current) if current else {}
    current_strikes = int(current_payload.get("strikes") or 0)
    current_warning_count = int(current_payload.get("warning_count") or 0)
    incident_strike_count = len(incident_history)

    latest_remaining = remaining_history[-1] if remaining_history else None
    max_remaining_strike = (
        max(int(row["strike_number"] or 0) for row in remaining_history) if remaining_history else None
    )
    if max_remaining_strike is not None:
        restored_strikes = max_remaining_strike
    else:
        restored_strikes = max(current_strikes - incident_strike_count, 0)

    warning_time = current_payload.get("warning_time")
    warning_in_window = _ts_in_window(warning_time, window)
    restored_warning_count = 0 if warning_in_window else current_warning_count
    restored_warning_time = None if warning_in_window else warning_time

    current_unban_time = current_payload.get("unban_time")
    if _ts_in_window(current_unban_time, window):
        restored_unban_time = None
    else:
        restored_unban_time = current_unban_time

    current_last_strike_time = current_payload.get("last_strike_time")
    if latest_remaining is not None:
        restored_last_strike_time = latest_remaining["timestamp"]
    elif _ts_in_window(current_last_strike_time, window):
        restored_last_strike_time = None
    else:
        restored_last_strike_time = current_last_strike_time

    preserve_remote_state = bool(restored_unban_time)
    if not preserve_remote_state:
        restriction_mode = "SQUAD"
        saved_traffic_limit_bytes = None
        saved_traffic_limit_strategy = None
        applied_traffic_limit_bytes = None
    else:
        restriction_mode = current_payload.get("restriction_mode") or "SQUAD"
        saved_traffic_limit_bytes = current_payload.get("saved_traffic_limit_bytes")
        saved_traffic_limit_strategy = current_payload.get("saved_traffic_limit_strategy")
        applied_traffic_limit_bytes = current_payload.get("applied_traffic_limit_bytes")

    delete_row = (
        restored_strikes <= 0
        and restored_warning_count <= 0
        and not restored_unban_time
        and not restored_warning_time
    )
    return {
        "delete_row": delete_row,
        "restored_strikes": restored_strikes,
        "restored_warning_count": restored_warning_count,
        "restored_warning_time": restored_warning_time,
        "restored_unban_time": restored_unban_time,
        "restored_last_strike_time": restored_last_strike_time,
        "restriction_mode": restriction_mode,
        "saved_traffic_limit_bytes": saved_traffic_limit_bytes,
        "saved_traffic_limit_strategy": saved_traffic_limit_strategy,
        "applied_traffic_limit_bytes": applied_traffic_limit_bytes,
        "incident_strike_count": incident_strike_count,
        "warning_in_window": warning_in_window,
    }


def _preview_item(conn: sqlite3.Connection, uuid: str, window: IncidentWindow) -> dict[str, Any]:
    current = _current_violation_row(conn, uuid)
    incident_history = _incident_history_rows(conn, uuid, window)
    remaining_history = _remaining_history_rows(conn, uuid, window)
    restored = _derive_restored_state(current, incident_history, remaining_history, window)
    return {
        "uuid": uuid,
        "current": dict(current) if current else None,
        "incident_history_count": len(incident_history),
        "remaining_history_count": len(remaining_history),
        "restored": restored,
    }


def _restore_remote_if_needed(container: Any, current: sqlite3.Row | None, uuid: str, window: IncidentWindow) -> dict[str, Any]:
    if current is None:
        return {"attempted": False, "enabled": False, "restored": False, "changed": False, "error": None}
    current_payload = dict(current)
    if not _ts_in_window(current_payload.get("unban_time"), window):
        return {"attempted": False, "enabled": False, "restored": False, "changed": False, "error": None}

    client = panel_client(container)
    if not client.enabled:
        return {
            "attempted": False,
            "enabled": False,
            "restored": False,
            "changed": False,
            "error": client.last_error or "Panel client is disabled",
        }

    result = restore_remote_restriction_state(client, uuid, container.runtime.settings, current_payload)
    return {
        "attempted": True,
        "enabled": True,
        "restored": bool(result.get("remote_updated", False)),
        "changed": bool(result.get("remote_changed", False)),
        "error": client.last_error,
    }


def _apply_uuid_reset(conn: sqlite3.Connection, container: Any, uuid: str, window: IncidentWindow) -> dict[str, Any]:
    current = _current_violation_row(conn, uuid)
    incident_history = _incident_history_rows(conn, uuid, window)
    remaining_history = _remaining_history_rows(conn, uuid, window)
    restored = _derive_restored_state(current, incident_history, remaining_history, window)
    remote = _restore_remote_if_needed(container, current, uuid, window)

    conn.execute(
        """
        DELETE FROM enforcement_jobs
        WHERE subject_uuid = ? AND created_at >= ? AND created_at <= ?
        """,
        (uuid, window.start, window.end),
    )
    conn.execute(
        """
        DELETE FROM violation_history
        WHERE uuid = ? AND timestamp >= ? AND timestamp <= ?
        """,
        (uuid, window.start, window.end),
    )

    if restored["delete_row"]:
        conn.execute("DELETE FROM violations WHERE uuid = ?", (uuid,))
    else:
        conn.execute(
            """
            INSERT INTO violations (
                uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count,
                restriction_mode, saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uuid) DO UPDATE SET
                strikes = excluded.strikes,
                unban_time = excluded.unban_time,
                last_forgiven = excluded.last_forgiven,
                last_strike_time = excluded.last_strike_time,
                warning_time = excluded.warning_time,
                warning_count = excluded.warning_count,
                restriction_mode = excluded.restriction_mode,
                saved_traffic_limit_bytes = excluded.saved_traffic_limit_bytes,
                saved_traffic_limit_strategy = excluded.saved_traffic_limit_strategy,
                applied_traffic_limit_bytes = excluded.applied_traffic_limit_bytes
            """,
            (
                uuid,
                restored["restored_strikes"],
                restored["restored_unban_time"],
                dict(current).get("last_forgiven") if current else None,
                restored["restored_last_strike_time"],
                restored["restored_warning_time"],
                restored["restored_warning_count"],
                restored["restriction_mode"],
                restored["saved_traffic_limit_bytes"],
                restored["saved_traffic_limit_strategy"],
                restored["applied_traffic_limit_bytes"],
            ),
        )

    return {
        "uuid": uuid,
        "current": dict(current) if current else None,
        "incident_history_count": len(incident_history),
        "remaining_history_count": len(remaining_history),
        "restored": restored,
        "remote_restore": remote,
    }


def run(start: str, end: str, runtime_dir: str | None, env_file: str | None, apply: bool) -> dict[str, Any]:
    window = IncidentWindow(start=_parse_iso8601(start), end=_parse_iso8601(end))
    if window.start > window.end:
        raise ValueError("--from must be earlier than or equal to --to")

    container = _load_container(runtime_dir, env_file)
    with container.store._connect() as conn:
        uuids = _collect_affected_uuids(conn, window)
        preview = [_preview_item(conn, uuid, window) for uuid in uuids]
        if not apply:
            return {
                "runtime_dir": str(container.runtime.runtime_dir),
                "db_path": container.runtime.db_path,
                "window": {"from": window.start, "to": window.end},
                "apply": False,
                "affected_uuid_count": len(uuids),
                "items": preview,
            }

        conn.execute("BEGIN IMMEDIATE")
        applied_items = [_apply_uuid_reset(conn, container, uuid, window) for uuid in uuids]
        conn.commit()
        return {
            "runtime_dir": str(container.runtime.runtime_dir),
            "db_path": container.runtime.db_path,
            "window": {"from": window.start, "to": window.end},
            "apply": True,
            "affected_uuid_count": len(uuids),
            "items": applied_items,
        }


def main() -> int:
    args = _parse_args()
    payload = run(args.start, args.end, args.runtime_dir, args.env_file, args.apply)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
