from __future__ import annotations

from typing import Any

from mobguard_platform.runtime_admin_defaults import ENFORCEMENT_SETTINGS_DEFAULTS

from ..context import APIContainer
from .runtime_state import load_runtime_config


def build_automation_status(container: APIContainer) -> dict[str, Any]:
    runtime_config = load_runtime_config(container)
    runtime_settings = runtime_config.get("settings", {}) if isinstance(runtime_config, dict) else {}
    store = getattr(container, "store", None)
    if store is not None and hasattr(store, "get_live_rules_state"):
        live_rules = store.get_live_rules_state().get("rules", {})
    else:
        live_rules = {}
    detection_settings = live_rules.get("settings", {}) if isinstance(live_rules.get("settings"), dict) else {}

    flags = {
        "dry_run": bool(runtime_settings.get("dry_run", ENFORCEMENT_SETTINGS_DEFAULTS["dry_run"])),
        "warning_only_mode": bool(
            runtime_settings.get("warning_only_mode", ENFORCEMENT_SETTINGS_DEFAULTS["warning_only_mode"])
        ),
        "manual_review_mixed_home_enabled": bool(
            runtime_settings.get(
                "manual_review_mixed_home_enabled",
                ENFORCEMENT_SETTINGS_DEFAULTS["manual_review_mixed_home_enabled"],
            )
        ),
        "manual_ban_approval_enabled": bool(
            runtime_settings.get(
                "manual_ban_approval_enabled",
                ENFORCEMENT_SETTINGS_DEFAULTS["manual_ban_approval_enabled"],
            )
        ),
        "shadow_mode": bool(detection_settings.get("shadow_mode", True)),
        "auto_enforce_requires_hard_or_multi_signal": bool(
            detection_settings.get("auto_enforce_requires_hard_or_multi_signal", True)
        ),
        "provider_conflict_review_only": bool(detection_settings.get("provider_conflict_review_only", True)),
    }

    mode_reasons: list[str] = []
    if flags["dry_run"]:
        mode_reasons.append("dry_run")
    if flags["shadow_mode"]:
        mode_reasons.append("shadow_mode")
    if flags["warning_only_mode"]:
        mode_reasons.append("warning_only_mode")

    if flags["dry_run"] or flags["shadow_mode"]:
        mode = "observe"
    elif flags["warning_only_mode"]:
        mode = "warning_only"
    else:
        mode = "enforce"

    return {
        "mode": mode,
        "mode_reasons": mode_reasons,
        "flags": flags,
    }


def build_enforcement_summary(container: APIContainer) -> dict[str, Any]:
    store = getattr(container, "store", None)
    automation_status = build_automation_status(container)
    runtime_config = load_runtime_config(container)
    runtime_settings = runtime_config.get("settings", {}) if isinstance(runtime_config, dict) else {}
    warning_timeout_seconds = int(
        runtime_settings.get(
            "warning_timeout_seconds",
            ENFORCEMENT_SETTINGS_DEFAULTS["warning_timeout_seconds"],
        )
        or ENFORCEMENT_SETTINGS_DEFAULTS["warning_timeout_seconds"]
    )
    if store is None:
        return {
            "active_total": 0,
            "active_warning_count": 0,
            "active_ban_count": 0,
            "last_warning_at": None,
            "last_ban_at": None,
            "last_ban_duration_minutes": None,
            "last_event_type": None,
            "last_event_at": None,
        }

    with store._connect() as conn:
        if not store._table_exists(conn, "violations"):
            return {
                "active_total": 0,
                "active_warning_count": 0,
                "active_ban_count": 0,
                "last_warning_at": None,
                "last_ban_at": None,
                "last_ban_duration_minutes": None,
                "last_event_type": None,
                "last_event_at": None,
            }

        active = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN warning_time IS NOT NULL
                             AND warning_time >= datetime('now', ?)
                             AND (unban_time IS NULL OR unban_time <= datetime('now'))
                            THEN 1 ELSE 0
                        END
                    ),
                    0
                ) AS active_warning_count,
                COALESCE(SUM(CASE WHEN unban_time IS NOT NULL AND unban_time > datetime('now') THEN 1 ELSE 0 END), 0)
                    AS active_ban_count,
                MAX(CASE WHEN warning_time IS NOT NULL THEN warning_time END) AS last_warning_at
            FROM violations
            """,
            (f"-{warning_timeout_seconds} seconds",),
        ).fetchone()

        last_ban_row = None
        if store._table_exists(conn, "violation_history"):
            last_ban_row = conn.execute(
                """
                SELECT timestamp, punishment_duration
                FROM violation_history
                ORDER BY timestamp DESC
                LIMIT 1
                """
            ).fetchone()

    last_warning_at = str(active["last_warning_at"] or "").strip() or None
    last_ban_at = str(last_ban_row["timestamp"] or "").strip() if last_ban_row else None
    last_ban_at = last_ban_at or None
    last_event_type = None
    last_event_at = None
    if last_warning_at and (not last_ban_at or last_warning_at >= last_ban_at):
        last_event_type = "warning"
        last_event_at = last_warning_at
    elif last_ban_at:
        last_event_type = "ban"
        last_event_at = last_ban_at

    active_warning_count = int(active["active_warning_count"] or 0)
    active_ban_count = int(active["active_ban_count"] or 0)

    return {
        "active_total": active_warning_count + active_ban_count,
        "active_warning_count": active_warning_count,
        "active_ban_count": active_ban_count,
        "last_warning_at": last_warning_at,
        "last_ban_at": last_ban_at,
        "last_ban_duration_minutes": (
            int(last_ban_row["punishment_duration"] or 0) if last_ban_row else None
        ),
        "last_event_type": last_event_type,
        "last_event_at": last_event_at,
        "automation_mode": automation_status.get("mode"),
        "warning_timeout_seconds": warning_timeout_seconds,
    }
