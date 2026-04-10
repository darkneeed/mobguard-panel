from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from ..context import APIContainer
from .runtime_state import (
    build_user_card,
    coerce_int_list,
    coerce_optional_int,
    panel_client,
    resolve_user_identity,
    search_runtime_users,
)


def search_users(container: APIContainer, query: str) -> dict[str, Any]:
    items = search_runtime_users(container.store, query)
    panel_match = panel_client(container).get_user_data(query)
    return {"items": items, "panel_match": panel_match}


def get_user_card(container: APIContainer, identifier: str) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    return build_user_card(container.store, identity)


def ban_user(container: APIContainer, identifier: str, minutes: int) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to ban a user")
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
            INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid, "", "", None, "manual_data_admin", strikes, minutes, now.isoformat()),
        )
        conn.commit()
    panel = panel_client(container)
    remote_updated = panel.toggle_user(uuid, False) if panel.enabled else False
    card = get_user_card(container, identifier)
    card["remote_updated"] = remote_updated
    return card


def unban_user(container: APIContainer, identifier: str) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to unban a user")
    with container.store._connect() as conn:
        conn.execute("DELETE FROM violations WHERE uuid = ?", (uuid,))
        conn.commit()
    panel = panel_client(container)
    remote_updated = panel.toggle_user(uuid, True) if panel.enabled else False
    card = get_user_card(container, identifier)
    card["remote_updated"] = remote_updated
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
        value = coerce_optional_int(identity.get("system_id"))
    elif kind == "telegram":
        key = "exempt_tg_ids"
        value = coerce_optional_int(identity.get("telegram_id"))
    else:
        raise HTTPException(status_code=400, detail="Unsupported exemption kind")
    if value is None:
        raise HTTPException(status_code=400, detail="Resolved user has no matching identifier for this exemption")
    state = container.store.get_live_rules_state()
    current_values = coerce_int_list(state["rules"].get(key, []))
    if enabled and value not in current_values:
        current_values.append(value)
    if not enabled:
        current_values = [item for item in current_values if item != value]
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
            SELECT uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count
            FROM violations
            ORDER BY COALESCE(unban_time, warning_time, last_strike_time) DESC
            LIMIT 200
            """
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


def list_overrides(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        unsure = []
        if container.store._table_exists(conn, "unsure_patterns"):
            unsure = conn.execute(
                """
                SELECT ip_pattern, decision, timestamp
                FROM unsure_patterns
                ORDER BY timestamp DESC
                """
            ).fetchall()
        exact_ip = conn.execute(
            """
            SELECT ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at
            FROM exact_ip_overrides
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return {"exact_ip": [dict(row) for row in exact_ip], "unsure_patterns": [dict(row) for row in unsure]}


def delete_exact_override(container: APIContainer, ip: str) -> dict[str, Any]:
    with container.store._connect() as conn:
        conn.execute("DELETE FROM exact_ip_overrides WHERE ip = ?", (ip,))
        conn.commit()
    return {"ok": True}


def upsert_unsure_override(container: APIContainer, ip: str, decision: str) -> dict[str, Any]:
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_patterns"):
            raise HTTPException(status_code=400, detail="unsure_patterns table is unavailable")
        conn.execute(
            """
            INSERT INTO unsure_patterns (ip_pattern, decision, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(ip_pattern) DO UPDATE SET decision = excluded.decision, timestamp = excluded.timestamp
            """,
            (ip, decision, now),
        )
        conn.commit()
    return {"ok": True, "ip": ip, "decision": decision}


def delete_unsure_override(container: APIContainer, ip: str) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_patterns"):
            return {"ok": True}
        conn.execute("DELETE FROM unsure_patterns WHERE ip_pattern = ?", (ip,))
        conn.commit()
    return {"ok": True}


def list_cache(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ip_decisions"):
            return {"items": []}
        rows = conn.execute(
            """
            SELECT ip, status, confidence, details, asn, expires, log_json, bundle_json
            FROM ip_decisions
            ORDER BY expires DESC
            LIMIT 200
            """
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


def patch_cache(container: APIContainer, ip: str, updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        raise HTTPException(status_code=400, detail="No cache fields provided")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ip_decisions"):
            raise HTTPException(status_code=400, detail="ip_decisions table is unavailable")
        conn.execute(f"UPDATE ip_decisions SET {assignments} WHERE ip = ?", [*updates.values(), ip])
        conn.commit()
        row = conn.execute(
            "SELECT ip, status, confidence, details, asn, expires, log_json, bundle_json FROM ip_decisions WHERE ip = ?",
            (ip,),
        ).fetchone()
    return dict(row) if row else {"ok": False}


def delete_cache(container: APIContainer, ip: str) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "ip_decisions"):
            return {"ok": True}
        conn.execute("DELETE FROM ip_decisions WHERE ip = ?", (ip,))
        conn.commit()
    return {"ok": True}


def get_learning_admin(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_learning"):
            return {"promoted_active": [], "promoted_stats": [], "legacy": []}
        promoted_active = conn.execute(
            """
            SELECT pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
            FROM learning_patterns_active
            ORDER BY support DESC, precision DESC
            LIMIT 200
            """
        ).fetchall()
        promoted_stats = conn.execute(
            """
            SELECT pattern_type, pattern_value, decision, support, total, precision, updated_at, metadata_json
            FROM learning_pattern_stats
            ORDER BY total DESC, precision DESC
            LIMIT 200
            """
        ).fetchall()
        legacy = conn.execute(
            """
            SELECT id, pattern_type, pattern_value, decision, confidence, timestamp
            FROM unsure_learning
            ORDER BY confidence DESC, timestamp DESC
            LIMIT 200
            """
        ).fetchall()
    return {
        "promoted_active": [dict(row) for row in promoted_active],
        "promoted_stats": [dict(row) for row in promoted_stats],
        "legacy": [dict(row) for row in legacy],
    }


def patch_legacy_learning(container: APIContainer, row_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        raise HTTPException(status_code=400, detail="No legacy learning fields provided")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_learning"):
            raise HTTPException(status_code=400, detail="unsure_learning table is unavailable")
        conn.execute(f"UPDATE unsure_learning SET {assignments} WHERE id = ?", [*updates.values(), row_id])
        conn.commit()
        row = conn.execute(
            "SELECT id, pattern_type, pattern_value, decision, confidence, timestamp FROM unsure_learning WHERE id = ?",
            (row_id,),
        ).fetchone()
    return dict(row) if row else {"ok": False}


def delete_legacy_learning(container: APIContainer, row_id: int) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_learning"):
            return {"ok": True}
        conn.execute("DELETE FROM unsure_learning WHERE id = ?", (row_id,))
        conn.commit()
    return {"ok": True}
