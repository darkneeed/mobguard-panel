from __future__ import annotations

import base64
import copy
import csv
import io
import json
from datetime import datetime, timedelta
from typing import Any
import zipfile

from fastapi import HTTPException

from mobguard_platform import (
    apply_remote_access_state,
    apply_remote_traffic_cap,
    normalize_restriction_mode,
    restore_remote_restriction_state,
    SQUAD_RESTRICTION_MODE,
)

from ..context import APIContainer
from .runtime_state import (
    build_user_export_payload,
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


def get_user_card_export(container: APIContainer, identifier: str) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    return build_user_export_payload(container.store, identifier, identity)


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


def _parse_export_date(value: str, *, end_of_day: bool) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format {value!r}, expected YYYY-MM-DD") from exc
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed.replace(microsecond=0).isoformat()


def _safe_json_loads(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _latest_resolution_join_sql(store: Any, conn: Any) -> str:
    if not store._table_exists(conn, "review_resolutions"):
        return "NULL AS final_resolution, NULL AS resolution_note, NULL AS resolution_created_at"
    return """
        (
            SELECT rr.resolution
            FROM review_resolutions rr
            WHERE rr.case_id = rc.id
            ORDER BY rr.created_at DESC, rr.id DESC
            LIMIT 1
        ) AS final_resolution,
        (
            SELECT rr.note
            FROM review_resolutions rr
            WHERE rr.case_id = rc.id
            ORDER BY rr.created_at DESC, rr.id DESC
            LIMIT 1
        ) AS resolution_note,
        (
            SELECT rr.created_at
            FROM review_resolutions rr
            WHERE rr.case_id = rc.id
            ORDER BY rr.created_at DESC, rr.id DESC
            LIMIT 1
            ) AS resolution_created_at
    """


def _ground_truth_for_resolution(final_resolution: str | None) -> str:
    if final_resolution in {"HOME", "MOBILE"}:
        return final_resolution
    if final_resolution == "SKIP":
        return "unknown"
    return "pending"


def _match_provider_profile(profiles: list[dict[str, Any]], isp: str, asn: Any) -> tuple[dict[str, Any] | None, list[str]]:
    searchable = str(isp or "").lower()
    best_profile: dict[str, Any] | None = None
    best_aliases: list[str] = []
    best_score = 0
    normalized_asn = coerce_optional_int(asn)
    for profile in profiles:
        aliases = [str(item).lower() for item in profile.get("aliases", []) if str(item).strip()]
        alias_hits = [alias for alias in aliases if alias in searchable]
        profile_asns = {coerce_optional_int(item) for item in profile.get("asns", [])}
        asn_hit = normalized_asn is not None and normalized_asn in profile_asns
        if not alias_hits and not asn_hit:
            continue
        score = (3 if asn_hit else 0) + len(alias_hits)
        if score > best_score:
            best_profile = profile
            best_aliases = alias_hits
            best_score = score
    return best_profile, best_aliases


def _normalize_provider_evidence(provider_evidence: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(provider_evidence or {})
    return {
        "provider_key": evidence.get("provider_key"),
        "provider_classification": evidence.get("provider_classification", "unknown"),
        "service_type_hint": evidence.get("service_type_hint", "unknown"),
        "service_conflict": bool(evidence.get("service_conflict", False)),
        "review_recommended": bool(evidence.get("review_recommended", False)),
        "matched_aliases": list(evidence.get("matched_aliases", [])),
        "provider_mobile_markers": list(evidence.get("provider_mobile_markers", evidence.get("mobile_markers", []))),
        "provider_home_markers": list(evidence.get("provider_home_markers", evidence.get("home_markers", []))),
    }


def _has_provider_evidence(provider_evidence: dict[str, Any]) -> bool:
    return bool(
        provider_evidence.get("provider_key")
        or provider_evidence.get("matched_aliases")
        or provider_evidence.get("provider_mobile_markers")
        or provider_evidence.get("provider_home_markers")
        or provider_evidence.get("service_type_hint") not in (None, "", "unknown")
    )


def _reconstruct_provider_evidence(
    provider_evidence: dict[str, Any],
    *,
    reasons: list[dict[str, Any]],
    rules_snapshot: dict[str, Any],
    isp: Any,
    asn: Any,
) -> tuple[dict[str, Any], bool]:
    if provider_evidence and provider_evidence.get("provider_key"):
        return _normalize_provider_evidence(provider_evidence), False

    reconstructed: dict[str, Any] = {}
    for reason in reasons:
        if not isinstance(reason, dict):
            continue
        metadata = reason.get("metadata") if isinstance(reason.get("metadata"), dict) else {}
        if metadata.get("provider_key"):
            reconstructed["provider_key"] = str(metadata.get("provider_key"))
            reconstructed["provider_classification"] = str(metadata.get("provider_classification") or "unknown")
            reconstructed["service_type_hint"] = str(metadata.get("service_type_hint") or "unknown")
            reconstructed["matched_aliases"] = list(metadata.get("matched_aliases") or [])
            reconstructed["provider_mobile_markers"] = list(metadata.get("mobile_markers") or [])
            reconstructed["provider_home_markers"] = list(metadata.get("home_markers") or [])
            reconstructed["service_conflict"] = reconstructed.get("service_type_hint") == "conflict"
            reconstructed["review_recommended"] = bool(reason.get("code") == "provider_review_guardrail")
            return _normalize_provider_evidence(reconstructed), True

    return _normalize_provider_evidence(provider_evidence), False


def _explainability_snapshot(reasons: list[dict[str, Any]], provider_evidence: dict[str, Any]) -> dict[str, Any]:
    home_sources = sorted(
        {
            str(reason.get("source") or "")
            for reason in reasons
            if str(reason.get("direction") or "").upper() == "HOME" and int(reason.get("weight") or 0) < 0
        }
    )
    mobile_sources = sorted(
        {
            str(reason.get("source") or "")
            for reason in reasons
            if str(reason.get("direction") or "").upper() == "MOBILE" and int(reason.get("weight") or 0) > 0
        }
    )
    service_type_hint = str(provider_evidence.get("service_type_hint") or "").lower()
    supporting_sources = set(home_sources if service_type_hint == "home" else mobile_sources if service_type_hint == "mobile" else [])
    supporting_sources.discard("provider_profile")
    supporting_sources.discard("generic_keyword")
    return {
        "home_sources": home_sources,
        "mobile_sources": mobile_sources,
        "provider_signal_only": service_type_hint in {"home", "mobile"} and not supporting_sources,
        "review_recommended": bool(provider_evidence.get("review_recommended")),
    }


def _reason_pattern(reason: dict[str, Any]) -> str:
    metadata = reason.get("metadata") if isinstance(reason.get("metadata"), dict) else {}
    if metadata.get("pattern_value"):
        return str(metadata["pattern_value"])
    if metadata.get("combo_key"):
        return str(metadata["combo_key"])
    if metadata.get("provider_key") and metadata.get("service_type_hint") in {"home", "mobile", "conflict"}:
        return f"{metadata['provider_key']}:{metadata['service_type_hint']}"
    if metadata.get("provider_key"):
        return str(metadata["provider_key"])
    if metadata.get("asn") is not None:
        return f"asn:{metadata['asn']}"
    keywords = metadata.get("keywords")
    if isinstance(keywords, list) and keywords:
        return "|".join(sorted(str(item) for item in keywords))
    return ""


def _csv_string(fieldnames: list[str], rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return stream.getvalue()


def _build_export_rules_snapshot(container: APIContainer) -> tuple[dict[str, Any], list[str], str]:
    warnings: list[str] = []
    live_rules_state = container.store.get_live_rules_state()
    snapshot_source = "live_rules"
    snapshot = copy.deepcopy(live_rules_state)
    runtime_rules = None
    if getattr(container, "runtime", None) is not None:
        runtime_rules = copy.deepcopy(container.runtime.reload_config())
    if runtime_rules is not None:
        live_profiles = live_rules_state["rules"].get("provider_profiles", [])
        runtime_profiles = runtime_rules.get("provider_profiles", [])
        if (not live_profiles) and runtime_profiles:
            snapshot["rules"]["provider_profiles"] = copy.deepcopy(runtime_profiles)
            snapshot["rules"].setdefault("settings", {}).update(
                {
                    key: value
                    for key, value in runtime_rules.get("settings", {}).items()
                    if key in {"provider_mobile_marker_bonus", "provider_home_marker_penalty", "provider_conflict_review_only"}
                }
            )
            snapshot_source = "runtime_merged"
            warnings.append("live_rules_stale_or_unseeded")
    return snapshot, warnings, snapshot_source


def _build_calibration_rows(container: APIContainer, filters: dict[str, Any]) -> list[dict[str, Any]]:
    rules_snapshot_state, snapshot_warnings, _ = _build_export_rules_snapshot(container)
    rules_snapshot = rules_snapshot_state.get("rules", {})
    store = container.store
    status = str(filters.get("status") or "resolved_only").lower()
    if status not in {"resolved_only", "open_only", "all"}:
        raise HTTPException(status_code=400, detail="status must be resolved_only, open_only or all")
    clauses: list[str] = []
    params: list[Any] = []
    if filters.get("opened_from"):
        clauses.append("rc.opened_at >= ?")
        params.append(_parse_export_date(str(filters["opened_from"]), end_of_day=False))
    if filters.get("opened_to"):
        clauses.append("rc.opened_at <= ?")
        params.append(_parse_export_date(str(filters["opened_to"]), end_of_day=True))
    if filters.get("review_reason"):
        clauses.append("rc.review_reason = ?")
        params.append(str(filters["review_reason"]))
    if status == "resolved_only":
        clauses.append("rc.status IN ('RESOLVED', 'SKIPPED')")
    elif status == "open_only":
        clauses.append("rc.status = 'OPEN'")

    with store._connect() as conn:
        if not store._table_exists(conn, "review_cases") or not store._table_exists(conn, "analysis_events"):
            return []
        query = [
            f"""
            SELECT
                rc.id AS case_id,
                rc.status,
                rc.review_reason,
                rc.opened_at,
                rc.updated_at,
                rc.score AS case_score,
                rc.verdict AS case_verdict,
                rc.confidence_band AS case_confidence_band,
                rc.reason_codes_json,
                rc.latest_event_id,
                ae.bundle_json,
                ae.reasons_json,
                ae.signal_flags_json,
                ae.score AS event_score,
                ae.isp,
                ae.asn,
                {_latest_resolution_join_sql(store, conn)}
            FROM review_cases rc
            JOIN analysis_events ae ON ae.id = rc.latest_event_id
            """
        ]
        if clauses:
            query.append("WHERE " + " AND ".join(clauses))
        query.append("ORDER BY rc.updated_at DESC")
        sql = " ".join(query)
        base_rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
        case_ids = [int(row["case_id"]) for row in base_rows]
        labels_map: dict[int, list[dict[str, Any]]] = {}
        if case_ids and store._table_exists(conn, "review_labels"):
            placeholders = ", ".join("?" for _ in case_ids)
            label_rows = conn.execute(
                f"""
                SELECT case_id, pattern_type, pattern_value, decision, created_at
                FROM review_labels
                WHERE case_id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                case_ids,
            ).fetchall()
            for label_row in label_rows:
                payload = dict(label_row)
                labels_map.setdefault(int(payload["case_id"]), []).append(payload)

    provider_key_filter = str(filters.get("provider_key") or "").strip().lower()
    export_rows: list[dict[str, Any]] = []
    for row in base_rows:
        reasons = _safe_json_loads(row.pop("reasons_json", None), [])
        signal_flags = _safe_json_loads(row.pop("signal_flags_json", None), {})
        bundle = _safe_json_loads(row.pop("bundle_json", None), {})
        if isinstance(bundle, dict):
            reasons = bundle.get("reasons", reasons)
            signal_flags = bundle.get("signal_flags", signal_flags)
        provider_evidence = signal_flags.get("provider_evidence") if isinstance(signal_flags, dict) else {}
        if not isinstance(provider_evidence, dict):
            provider_evidence = {}

        final_resolution = row.get("final_resolution")
        ground_truth = _ground_truth_for_resolution(str(final_resolution) if final_resolution else None)
        provider_evidence, reconstructed = _reconstruct_provider_evidence(
            provider_evidence,
            reasons=reasons if isinstance(reasons, list) else [],
            rules_snapshot=rules_snapshot,
            isp=row.get("isp"),
            asn=row.get("asn"),
        )
        provider_key = str(provider_evidence.get("provider_key") or "").strip().lower()
        if provider_key_filter and provider_key != provider_key_filter:
            continue
        dataset_warning_flags = list(snapshot_warnings)
        if not final_resolution:
            dataset_warning_flags.append("pending_resolution")
        if not provider_evidence.get("provider_key"):
            dataset_warning_flags.append("provider_explainability_missing")
        export_rows.append(
            {
                "case_id": int(row["case_id"]),
                "opened_at": row.get("opened_at"),
                "updated_at": row.get("updated_at"),
                "review_reason": row.get("review_reason"),
                "score": row.get("event_score") if row.get("event_score") is not None else row.get("case_score"),
                "verdict_before_review": row.get("case_verdict"),
                "confidence_band": row.get("case_confidence_band"),
                "final_resolution": final_resolution,
                "ground_truth": ground_truth,
                "asn": row.get("asn"),
                "isp": row.get("isp"),
                "provider_evidence": provider_evidence,
                "provider_evidence_reconstructed": reconstructed,
                "reason_codes": _safe_json_loads(row.get("reason_codes_json"), []),
                "reasons": reasons if isinstance(reasons, list) else [],
                "review_labels": labels_map.get(int(row["case_id"]), []),
                "dataset_warning_flags": sorted(set(dataset_warning_flags)),
                "explainability": _explainability_snapshot(
                    reasons if isinstance(reasons, list) else [],
                    provider_evidence,
                ),
            }
        )
    return export_rows


def _build_provider_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        evidence = row.get("provider_evidence", {})
        provider_key = str(evidence.get("provider_key") or "unknown")
        service_hint = str(evidence.get("service_type_hint") or "unknown")
        key = (provider_key, service_hint)
        bucket = buckets.setdefault(
            key,
            {
                "provider_key": provider_key,
                "service_type_hint": service_hint,
                "raw_total": 0,
                "known_total": 0,
                "home": 0,
                "mobile": 0,
                "unknown": 0,
                "conflicts": 0,
                "conflict_rate": 0.0,
            },
        )
        bucket["raw_total"] += 1
        if row["ground_truth"] == "HOME":
            bucket["known_total"] += 1
            bucket["home"] += 1
        elif row["ground_truth"] == "MOBILE":
            bucket["known_total"] += 1
            bucket["mobile"] += 1
        else:
            bucket["unknown"] += 1
        if evidence.get("service_conflict"):
            bucket["conflicts"] += 1
    for bucket in buckets.values():
        bucket["conflict_rate"] = round(bucket["conflicts"] / bucket["raw_total"], 4) if bucket["raw_total"] else 0.0
    return sorted(buckets.values(), key=lambda item: (-int(item["raw_total"]), item["provider_key"], item["service_type_hint"]))


def _build_feature_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if row["ground_truth"] not in {"HOME", "MOBILE"}:
            continue
        for reason in row.get("reasons", []):
            if not isinstance(reason, dict):
                continue
            direction = str(reason.get("direction") or "").upper()
            if direction not in {"HOME", "MOBILE"}:
                continue
            key = (
                str(reason.get("code") or ""),
                str(reason.get("source") or ""),
                _reason_pattern(reason),
            )
            bucket = buckets.setdefault(
                key,
                {
                    "reason_code": key[0],
                    "source": key[1],
                    "pattern": key[2],
                    "support": 0,
                    "total": 0,
                    "precision": 0.0,
                },
            )
            bucket["total"] += 1
            if direction == row["ground_truth"]:
                bucket["support"] += 1
    for bucket in buckets.values():
        bucket["precision"] = round(bucket["support"] / bucket["total"], 4) if bucket["total"] else 0.0
    return sorted(buckets.values(), key=lambda item: (-float(item["precision"]), -int(item["support"]), item["reason_code"]))


def _build_mixed_provider_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        evidence = row.get("provider_evidence", {})
        if str(evidence.get("provider_classification") or "").lower() != "mixed":
            continue
        provider_key = str(evidence.get("provider_key") or "unknown")
        bucket = buckets.setdefault(
            provider_key,
            {
                "provider_key": provider_key,
                "raw_total": 0,
                "conflicts": 0,
                "known_total": 0,
                "correct_service_hint": 0,
                "resolved_precision": 0.0,
            },
        )
        bucket["raw_total"] += 1
        if evidence.get("service_conflict"):
            bucket["conflicts"] += 1
        service_hint = str(evidence.get("service_type_hint") or "").lower()
        if row["ground_truth"] in {"HOME", "MOBILE"} and service_hint in {"home", "mobile"}:
            bucket["known_total"] += 1
            if service_hint == row["ground_truth"].lower():
                bucket["correct_service_hint"] += 1
    for bucket in buckets.values():
        bucket["resolved_precision"] = round(
            bucket["correct_service_hint"] / bucket["known_total"], 4
        ) if bucket["known_total"] else 0.0
    return sorted(buckets.values(), key=lambda item: (-int(item["raw_total"]), -float(item["resolved_precision"]), item["provider_key"]))


def _build_review_reason_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("review_reason") or "unknown")
        bucket = buckets.setdefault(
            key,
            {
                "review_reason": key,
                "total": 0,
                "home": 0,
                "mobile": 0,
                "unknown": 0,
            },
        )
        bucket["total"] += 1
        if row["ground_truth"] == "HOME":
            bucket["home"] += 1
        elif row["ground_truth"] == "MOBILE":
            bucket["mobile"] += 1
        else:
            bucket["unknown"] += 1
    return sorted(buckets.values(), key=lambda item: (-int(item["total"]), item["review_reason"]))


def _readiness_ratio(current: float, target: float) -> float:
    if target <= 0:
        return 1.0
    return max(0.0, min(float(current) / float(target), 1.0))


def _readiness_check(key: str, scope: str, current: float, target: float) -> dict[str, Any]:
    ratio = _readiness_ratio(current, target)
    return {
        "key": key,
        "scope": scope,
        "current": current,
        "target": target,
        "ratio": round(ratio, 4),
        "percent": int(round(ratio * 100)),
        "ready": ratio >= 1.0,
    }


def _build_calibration_artifacts(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    rules_snapshot, manifest_warnings, snapshot_source = _build_export_rules_snapshot(container)
    rows = _build_calibration_rows(container, filters)
    include_unknown = bool(filters.get("include_unknown", False))
    resolved_rows = [row for row in rows if row["ground_truth"] in {"HOME", "MOBILE", "unknown"}]
    known_rows = [row for row in rows if row["ground_truth"] in {"HOME", "MOBILE"}]
    aggregate_rows = rows if include_unknown else known_rows
    unknown_count = sum(1 for row in rows if row["ground_truth"] == "unknown")
    pending_count = sum(1 for row in rows if row["ground_truth"] == "pending")
    resolved_ratio = round(len(resolved_rows) / len(rows), 4) if rows else 0.0
    pending_ratio = round(pending_count / len(rows), 4) if rows else 0.0
    unknown_ratio = round(unknown_count / len(rows), 4) if rows else 0.0
    resolved_provider_rows = known_rows
    provider_evidence_count = sum(
        1 for row in resolved_provider_rows if _has_provider_evidence(row.get("provider_evidence", {}))
    )
    provider_key_count = sum(
        1 for row in resolved_provider_rows if (row.get("provider_evidence") or {}).get("provider_key")
    )
    provider_evidence_coverage = (
        round(provider_evidence_count / len(resolved_provider_rows), 4) if resolved_provider_rows else 0.0
    )
    provider_key_coverage = (
        round(provider_key_count / len(resolved_provider_rows), 4) if resolved_provider_rows else 0.0
    )
    provider_profiles_count = len(rules_snapshot.get("rules", {}).get("provider_profiles", []))
    provider_support_counts: dict[str, int] = {}
    for row in known_rows:
        evidence = row.get("provider_evidence", {})
        provider_key = str(evidence.get("provider_key") or "").strip().lower()
        service_hint = str(evidence.get("service_type_hint") or "").strip().lower()
        if not provider_key:
            continue
        pattern_key = f"{provider_key}:{service_hint}" if service_hint else provider_key
        provider_support_counts[pattern_key] = provider_support_counts.get(pattern_key, 0) + 1
    min_provider_support = min(provider_support_counts.values()) if provider_support_counts else 0
    warnings = list(manifest_warnings)
    if provider_profiles_count == 0:
        warnings.append("provider_profiles_missing")
    if provider_key_coverage == 0:
        warnings.append("provider_key_coverage_zero")
    if provider_evidence_coverage == 0:
        warnings.append("provider_explainability_missing")
    if resolved_ratio < 0.5:
        warnings.append("resolved_ratio_below_threshold")
    if provider_profiles_count > 0 and provider_key_coverage < 0.6:
        warnings.append("provider_key_coverage_below_target")
    if provider_support_counts and min_provider_support < 5:
        warnings.append("provider_support_below_target")
    dataset_ready = not (
        provider_profiles_count == 0 or provider_key_coverage == 0 or resolved_ratio < 0.5
    )
    tuning_ready = bool(
        provider_profiles_count > 0
        and provider_key_coverage >= 0.6
        and provider_support_counts
        and min_provider_support >= 5
    )
    dataset_checks = [
        _readiness_check(
            "provider_profiles_present",
            "dataset",
            1 if provider_profiles_count > 0 else 0,
            1,
        ),
        _readiness_check("resolved_ratio", "dataset", resolved_ratio, 0.5),
        _readiness_check("provider_evidence_coverage", "dataset", provider_evidence_coverage, 0.6),
        _readiness_check("provider_key_coverage", "dataset", provider_key_coverage, 0.6),
    ]
    tuning_checks = [
        _readiness_check(
            "provider_profiles_present",
            "tuning",
            1 if provider_profiles_count > 0 else 0,
            1,
        ),
        _readiness_check("provider_key_coverage", "tuning", provider_key_coverage, 0.6),
        _readiness_check("min_provider_support", "tuning", min_provider_support, 5),
    ]
    all_checks = dataset_checks + tuning_checks
    dataset_percent = int(round(sum(check["percent"] for check in dataset_checks) / len(dataset_checks))) if dataset_checks else 0
    tuning_percent = int(round(sum(check["percent"] for check in tuning_checks) / len(tuning_checks))) if tuning_checks else 0
    blockers = list(dict.fromkeys(check["key"] for check in all_checks if not check["ready"]))
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
        "snapshot_source": snapshot_source,
        "dataset_ready": dataset_ready,
        "tuning_ready": tuning_ready,
        "warnings": sorted(set(warnings)),
        "readiness": {
            "overall_percent": min(dataset_percent, tuning_percent),
            "dataset_percent": dataset_percent,
            "tuning_percent": tuning_percent,
            "blockers": blockers,
            "checks": all_checks,
        },
        "filters": {
            "opened_from": filters.get("opened_from"),
            "opened_to": filters.get("opened_to"),
            "review_reason": filters.get("review_reason"),
            "provider_key": filters.get("provider_key"),
            "include_unknown": include_unknown,
            "status": filters.get("status") or "resolved_only",
        },
        "row_counts": {
            "raw_rows": len(rows),
            "resolved_known_rows": len(known_rows),
            "resolved_unknown_rows": unknown_count,
            "open_rows": pending_count,
            "known_rows": len(known_rows),
            "aggregate_rows": len(aggregate_rows),
            "unknown_rows": unknown_count,
            "unknown_ratio": unknown_ratio,
        },
        "coverage": {
            "resolved_ratio": resolved_ratio,
            "pending_ratio": pending_ratio,
            "unknown_ratio": unknown_ratio,
            "provider_evidence_coverage": provider_evidence_coverage,
            "provider_key_coverage": provider_key_coverage,
            "provider_profiles_count": provider_profiles_count,
            "provider_pattern_candidates": len(provider_support_counts),
            "min_provider_support": min_provider_support,
        },
    }
    provider_summary = _build_provider_summary(rows)
    feature_summary = _build_feature_summary(known_rows)
    mixed_provider_summary = _build_mixed_provider_summary(rows)
    review_reason_summary = _build_review_reason_summary(rows)
    return {
        "rules_snapshot": rules_snapshot,
        "rows": rows,
        "known_rows": known_rows,
        "manifest": manifest,
        "provider_summary": provider_summary,
        "feature_summary": feature_summary,
        "mixed_provider_summary": mixed_provider_summary,
        "review_reason_summary": review_reason_summary,
    }


def build_calibration_preview(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    artifacts = _build_calibration_artifacts(container, filters)
    return artifacts["manifest"]


def build_calibration_export(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    artifacts = _build_calibration_artifacts(container, filters)
    rows = artifacts["rows"]
    manifest = artifacts["manifest"]
    rules_snapshot = artifacts["rules_snapshot"]
    provider_summary = artifacts["provider_summary"]
    feature_summary = artifacts["feature_summary"]
    mixed_provider_summary = artifacts["mixed_provider_summary"]
    review_reason_summary = artifacts["review_reason_summary"]

    archive_buffer = io.BytesIO()
    with io.StringIO() as jsonl_stream:
        for row in rows:
            jsonl_stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        calibration_jsonl = jsonl_stream.getvalue()

    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("rules_snapshot.json", json.dumps(rules_snapshot, ensure_ascii=False, indent=2))
        archive.writestr("calibration_rows.jsonl", calibration_jsonl)
        archive.writestr(
            "provider_summary.csv",
            _csv_string(
                ["provider_key", "service_type_hint", "raw_total", "known_total", "home", "mobile", "unknown", "conflicts", "conflict_rate"],
                provider_summary,
            ),
        )
        archive.writestr(
            "feature_summary.csv",
            _csv_string(
                ["reason_code", "source", "pattern", "support", "total", "precision"],
                feature_summary,
            ),
        )
        archive.writestr(
            "mixed_provider_summary.csv",
            _csv_string(
                ["provider_key", "raw_total", "conflicts", "known_total", "correct_service_hint", "resolved_precision"],
                mixed_provider_summary,
            ),
        )
        archive.writestr(
            "review_reason_summary.csv",
            _csv_string(
                ["review_reason", "total", "home", "mobile", "unknown"],
                review_reason_summary,
            ),
        )

    filename = f"mobguard-calibration-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.zip"
    manifest_header = base64.b64encode(json.dumps(manifest, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return {
        "content": archive_buffer.getvalue(),
        "filename": filename,
        "manifest": manifest,
        "manifest_header": manifest_header,
    }


def get_learning_admin(container: APIContainer) -> dict[str, Any]:
    with container.store._connect() as conn:
        if not container.store._table_exists(conn, "unsure_learning"):
            return {
                "promoted_active": [],
                "promoted_stats": [],
                "legacy": [],
                "promoted_provider_active": [],
                "promoted_provider_service_active": [],
                "promoted_provider_stats": [],
                "promoted_provider_service_stats": [],
                "legacy_provider": [],
                "legacy_provider_service": [],
            }
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
    promoted_active_rows = [dict(row) for row in promoted_active]
    promoted_stats_rows = [dict(row) for row in promoted_stats]
    legacy_rows = [dict(row) for row in legacy]
    return {
        "promoted_active": promoted_active_rows,
        "promoted_stats": promoted_stats_rows,
        "legacy": legacy_rows,
        "promoted_provider_active": [
            row for row in promoted_active_rows if row.get("pattern_type") == "provider"
        ],
        "promoted_provider_service_active": [
            row for row in promoted_active_rows if row.get("pattern_type") == "provider_service"
        ],
        "promoted_provider_stats": [
            row for row in promoted_stats_rows if row.get("pattern_type") == "provider"
        ],
        "promoted_provider_service_stats": [
            row for row in promoted_stats_rows if row.get("pattern_type") == "provider_service"
        ],
        "legacy_provider": [row for row in legacy_rows if row.get("pattern_type") == "provider"],
        "legacy_provider_service": [
            row for row in legacy_rows if row.get("pattern_type") == "provider_service"
        ],
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
