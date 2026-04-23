from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from mobguard_platform import (
    apply_remote_access_state,
    apply_remote_traffic_cap,
    normalize_restriction_mode,
    restore_remote_restriction_state,
    SQUAD_RESTRICTION_MODE,
)

from ..context import APIContainer
from .data_admin_exports import build_calibration_export, build_calibration_preview
from .data_admin_learning import (
    delete_legacy_learning,
    get_learning_admin,
    patch_legacy_learning,
)
from .data_admin_overrides_cache import (
    delete_cache,
    delete_exact_override,
    delete_unsure_override,
    list_cache,
    list_overrides,
    patch_cache,
    upsert_unsure_override,
)
from .data_admin_user_cards import (
    get_user_card as _get_user_card_impl,
    get_user_card_export as _get_user_card_export_impl,
    search_users as _search_users_impl,
)
from .runtime_state import (
    list_analysis_events as _list_analysis_events_impl,
    coerce_int_list,
    panel_client,
    resolve_user_identity,
)


def search_users(container: APIContainer, query: str) -> dict[str, Any]:
    return _search_users_impl(container, query)


def get_user_card(container: APIContainer, identifier: str) -> dict[str, Any]:
    return _get_user_card_impl(container, identifier)


def get_user_card_export(container: APIContainer, identifier: str) -> dict[str, Any]:
    return _get_user_card_export_impl(container, identifier)


def list_admin_audit(container: APIContainer, limit: int = 100) -> dict[str, Any]:
    return {"items": container.store.list_admin_audit_events(limit=limit)}


def list_analysis_events(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    return _list_analysis_events_impl(container.store, filters)


def _runtime_settings(container: APIContainer) -> dict[str, Any]:
    return container.runtime.config.get("settings", {})


def _ensure_manual_traffic_cap_overrides_table(conn: Any) -> None:
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


def _default_restriction_state() -> dict[str, Any]:
    return {
        "restriction_mode": SQUAD_RESTRICTION_MODE,
        "saved_traffic_limit_bytes": None,
        "saved_traffic_limit_strategy": None,
        "applied_traffic_limit_bytes": None,
    }


def _violation_select(conn: Any) -> str:
    violation_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(violations)").fetchall()
    }
    fields = [
        "uuid",
        "strikes",
        "unban_time",
        "last_forgiven",
        "last_strike_time",
        "warning_time",
        "warning_count",
    ]
    for optional_column in (
        "restriction_mode",
        "saved_traffic_limit_bytes",
        "saved_traffic_limit_strategy",
        "applied_traffic_limit_bytes",
    ):
        if optional_column in violation_columns:
            fields.append(optional_column)
        else:
            fields.append(f"NULL AS {optional_column}")
    return ", ".join(fields)


def _get_violation_restriction_state(conn: Any, uuid: str) -> dict[str, Any]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'violations'"
    ).fetchone()
    if not exists:
        return _default_restriction_state()
    row = conn.execute(
        f"SELECT {_violation_select(conn)} FROM violations WHERE uuid = ?",
        (uuid,),
    ).fetchone()
    if not row:
        return _default_restriction_state()
    payload = dict(row)
    payload["restriction_mode"] = normalize_restriction_mode(payload.get("restriction_mode"))
    return payload


def ban_user(container: APIContainer, identifier: str, minutes: int) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to restrict user access")
    now = datetime.utcnow().replace(microsecond=0)
    with container.store._connect() as conn:
        row = conn.execute("SELECT strikes FROM violations WHERE uuid = ?", (uuid,)).fetchone()
        strikes = max(int(row["strikes"]) if row else 0, 1)
        unban_time = now + timedelta(minutes=minutes)
        conn.execute(
            """
            INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
            VALUES (?, ?, ?, ?, ?, NULL, 0)
            ON CONFLICT(uuid) DO UPDATE SET
                strikes = excluded.strikes,
                unban_time = excluded.unban_time,
                last_forgiven = excluded.last_forgiven,
                last_strike_time = excluded.last_strike_time,
                warning_time = NULL,
                warning_count = 0
            """,
            (uuid, strikes, unban_time.isoformat(), now.isoformat(), now.isoformat()),
        )
        conn.execute(
            """
            UPDATE violations
            SET restriction_mode = ?, saved_traffic_limit_bytes = NULL,
                saved_traffic_limit_strategy = NULL, applied_traffic_limit_bytes = NULL
            WHERE uuid = ?
            """,
            (SQUAD_RESTRICTION_MODE, uuid),
        )
        conn.execute(
            """
            INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid, "", "", None, "manual_data_admin", strikes, minutes, now.isoformat()),
        )
        conn.commit()
    panel = panel_client(container)
    remote_updated = apply_remote_access_state(
        panel,
        uuid,
        _runtime_settings(container),
        restricted=True,
    ) if panel.enabled else False
    card = get_user_card(container, identifier)
    card["remote_updated"] = remote_updated
    if panel.last_error:
        card["remote_error"] = panel.last_error
    return card


def unban_user(container: APIContainer, identifier: str) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to restore full user access")
    with container.store._connect() as conn:
        restriction_state = _get_violation_restriction_state(conn, uuid)
    panel = panel_client(container)
    restore_result = restore_remote_restriction_state(
        panel,
        uuid,
        _runtime_settings(container),
        restriction_state,
    ) if panel.enabled else {"remote_updated": False, "remote_changed": False}
    remote_updated = bool(restore_result["remote_updated"])
    if remote_updated or not panel.enabled:
        with container.store._connect() as conn:
            conn.execute("DELETE FROM violations WHERE uuid = ?", (uuid,))
            conn.commit()
    card = get_user_card(container, identifier)
    card["remote_updated"] = remote_updated
    card["remote_changed"] = bool(restore_result.get("remote_changed", False))
    if panel.last_error:
        card["remote_error"] = panel.last_error
    return card


def apply_user_traffic_cap(container: APIContainer, identifier: str, gigabytes: int) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to apply traffic cap")
    panel = panel_client(container)
    if not panel.enabled:
        raise HTTPException(status_code=409, detail="Panel client is disabled")
    panel_user = identity.get("panel_user") or panel.get_user_data(uuid)
    try:
        cap_result = apply_remote_traffic_cap(panel, uuid, panel_user, gigabytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if cap_result["remote_updated"] and cap_result["remote_changed"]:
        now = datetime.utcnow().replace(microsecond=0).isoformat()
        with container.store._connect() as conn:
            _ensure_manual_traffic_cap_overrides_table(conn)
            conn.execute(
                """
                INSERT INTO manual_traffic_cap_overrides (
                    uuid, saved_traffic_limit_bytes, saved_traffic_limit_strategy,
                    applied_traffic_limit_bytes, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    saved_traffic_limit_bytes = excluded.saved_traffic_limit_bytes,
                    saved_traffic_limit_strategy = excluded.saved_traffic_limit_strategy,
                    applied_traffic_limit_bytes = excluded.applied_traffic_limit_bytes,
                    updated_at = excluded.updated_at
                """,
                (
                    uuid,
                    cap_result["saved_traffic_limit_bytes"],
                    cap_result["saved_traffic_limit_strategy"],
                    cap_result["applied_traffic_limit_bytes"],
                    now,
                ),
            )
            conn.commit()

    card = get_user_card(container, identifier)
    card["remote_updated"] = bool(cap_result["remote_updated"])
    card["remote_changed"] = bool(cap_result["remote_changed"])
    card["traffic_cap"] = {
        "gigabytes": gigabytes,
        "used_traffic_bytes": cap_result["used_traffic_bytes"],
        "target_limit_bytes": cap_result["target_limit_bytes"],
        "applied_traffic_limit_bytes": cap_result["applied_traffic_limit_bytes"],
        "preserved_existing_limit": bool(cap_result["preserved_existing_limit"]),
    }
    if panel.last_error:
        card["remote_error"] = panel.last_error
    return card


def restore_user_traffic_cap(container: APIContainer, identifier: str) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to restore traffic cap")
    panel = panel_client(container)
    if not panel.enabled:
        raise HTTPException(status_code=409, detail="Panel client is disabled")

    with container.store._connect() as conn:
        _ensure_manual_traffic_cap_overrides_table(conn)
        row = conn.execute(
            """
            SELECT saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
            FROM manual_traffic_cap_overrides
            WHERE uuid = ?
            """,
            (uuid,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No saved manual traffic cap override")

    state = {
        "restriction_mode": normalize_restriction_mode("TRAFFIC_CAP"),
        "saved_traffic_limit_bytes": row["saved_traffic_limit_bytes"],
        "saved_traffic_limit_strategy": row["saved_traffic_limit_strategy"],
        "applied_traffic_limit_bytes": row["applied_traffic_limit_bytes"],
    }
    restore_result = restore_remote_restriction_state(
        panel,
        uuid,
        _runtime_settings(container),
        state,
    )
    if restore_result["remote_updated"]:
        with container.store._connect() as conn:
            _ensure_manual_traffic_cap_overrides_table(conn)
            conn.execute("DELETE FROM manual_traffic_cap_overrides WHERE uuid = ?", (uuid,))
            conn.commit()

    card = get_user_card(container, identifier)
    card["remote_updated"] = bool(restore_result["remote_updated"])
    card["remote_changed"] = bool(restore_result.get("remote_changed", False))
    if panel.last_error:
        card["remote_error"] = panel.last_error
    return card


def update_user_warnings(container: APIContainer, identifier: str, action: str, count: int) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to update warnings")
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    with container.store._connect() as conn:
        row = conn.execute("SELECT strikes FROM violations WHERE uuid = ?", (uuid,)).fetchone()
        strikes = int(row["strikes"]) if row else 0
        if action == "clear":
            conn.execute(
                """
                INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
                VALUES (?, ?, NULL, NULL, NULL, NULL, 0)
                ON CONFLICT(uuid) DO UPDATE SET warning_time = NULL, warning_count = 0
                """,
                (uuid, strikes),
            )
        elif action == "set":
            conn.execute(
                """
                INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
                VALUES (?, ?, NULL, NULL, NULL, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET warning_time = excluded.warning_time, warning_count = excluded.warning_count
                """,
                (uuid, strikes, now, count),
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported warning action")
        conn.commit()
    return get_user_card(container, identifier)


def update_user_strikes(container: APIContainer, identifier: str, action: str, count: int) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to update strikes")
    with container.store._connect() as conn:
        row = conn.execute(
            "SELECT strikes, unban_time, warning_time, warning_count FROM violations WHERE uuid = ?",
            (uuid,),
        ).fetchone()
        current_strikes = int(row["strikes"]) if row else 0
        if action == "add":
            next_strikes = current_strikes + count
        elif action == "remove":
            next_strikes = max(current_strikes - count, 0)
        elif action == "set":
            next_strikes = count
        else:
            raise HTTPException(status_code=400, detail="Unsupported strike action")
        if next_strikes == 0:
            conn.execute("DELETE FROM violations WHERE uuid = ?", (uuid,))
        else:
            conn.execute(
                """
                INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
                VALUES (?, ?, ?, NULL, NULL, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET strikes = excluded.strikes
                """,
                (
                    uuid,
                    next_strikes,
                    row["unban_time"] if row else None,
                    row["warning_time"] if row else None,
                    int(row["warning_count"]) if row else 0,
                ),
            )
        conn.commit()
    return get_user_card(container, identifier)


def update_user_exemptions(container: APIContainer, identifier: str, kind: str, enabled: bool, session: dict[str, Any]) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    if kind == "system":
        key = "exempt_ids"
        value = coerce_int_list([identity.get("system_id")])
    elif kind == "telegram":
        key = "exempt_tg_ids"
        value = coerce_int_list([identity.get("telegram_id")])
    else:
        raise HTTPException(status_code=400, detail="Unsupported exemption kind")
    if not value:
        raise HTTPException(status_code=400, detail="Resolved user has no matching identifier for this exemption")
    state = container.store.get_live_rules_state()
    current_values = coerce_int_list(state["rules"].get(key, []))
    target_value = value[0]
    if enabled and target_value not in current_values:
        current_values.append(target_value)
    if not enabled:
        current_values = [item for item in current_values if item != target_value]
    container.store.update_live_rules(
        {key: current_values},
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
    )
    return get_user_card(container, identifier)


def list_violations(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "violations") or not container.store._table_exists(conn, "violation_history"):
            return {"active": [], "history": []}
        active = conn.execute(
            """
            SELECT {columns}
            FROM violations
            ORDER BY COALESCE(unban_time, warning_time, last_strike_time) DESC
            LIMIT 200
            """.format(columns=_violation_select(conn))
        ).fetchall()
        history = conn.execute(
            """
            SELECT id, uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp
            FROM violation_history
            ORDER BY timestamp DESC
            LIMIT 200
            """
        ).fetchall()
    return {"active": [dict(row) for row in active], "history": [dict(row) for row in history]}
