from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


def _utcnow() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


@dataclass(frozen=True)
class LimiterDecision:
    allowed: bool
    reason: str
    scope_key: str
    event_count: int
    threshold: int
    cooldown_active: bool
    cooldown_until: str | None
    rollout_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "scope_key": self.scope_key,
            "event_count": self.event_count,
            "threshold": self.threshold,
            "cooldown_active": self.cooldown_active,
            "cooldown_until": self.cooldown_until,
            "rollout_mode": self.rollout_mode,
        }


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _group_scope_key(settings: dict[str, Any], user_data: dict[str, Any], payload: dict[str, Any], bundle: Any) -> str:
    uuid = str(user_data.get("uuid") or "").strip()
    if uuid:
        return f"uuid:{uuid}"
    if bool(settings.get("limiter_group_by_asn", True)) and bundle is not None and getattr(bundle, "asn", None):
        return f"asn:{int(getattr(bundle, 'asn'))}"
    ip = str(payload.get("ip") or "").strip()
    if bool(settings.get("limiter_group_by_subnet", True)) and ip and "." in ip:
        return f"subnet:{ip.rsplit('.', 1)[0]}"
    return f"ip:{ip or 'unknown'}"


def _load_ignore(conn: Any, scope_key: str, now_iso: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT scope_key, reason, expires_at
        FROM limiter_ignore_rules
        WHERE scope_key = ?
        """,
        (scope_key,),
    ).fetchone()
    if not row:
        return None
    expires_at = str(row["expires_at"] or "").strip()
    if expires_at and expires_at <= now_iso:
        conn.execute("DELETE FROM limiter_ignore_rules WHERE scope_key = ?", (scope_key,))
        return None
    return {"scope_key": scope_key, "reason": str(row["reason"] or "ignore"), "expires_at": expires_at}


def evaluate_limiter_policy_tx(
    conn: Any,
    settings: dict[str, Any],
    user_data: dict[str, Any],
    payload: dict[str, Any],
    bundle: Any,
    *,
    action: str = "enforcement",
) -> LimiterDecision:
    enabled = bool(settings.get("limiter_enabled", False))
    rollout_mode = str(settings.get("limiter_rollout_mode") or "observe").strip().lower()
    if rollout_mode not in {"observe", "warning_only", "enforce"}:
        rollout_mode = "observe"
    if not enabled:
        return LimiterDecision(True, "disabled", "", 0, 0, False, None, rollout_mode)

    now = _utcnow()
    now_iso = now.isoformat()
    scope_key = _group_scope_key(settings, user_data, payload, bundle)
    ignored = _load_ignore(conn, scope_key, now_iso)
    if ignored:
        return LimiterDecision(
            False,
            "ignore_ttl",
            scope_key,
            0,
            0,
            False,
            None,
            rollout_mode,
        )

    threshold_base = max(_safe_int(settings.get("limiter_threshold_count"), 3), 1)
    tolerance = max(_safe_int(settings.get("limiter_tolerance"), 0), 0)
    tolerance_multiplier = max(_safe_float(settings.get("limiter_tolerance_multiplier"), 1.0), 0.0)
    threshold = threshold_base + int(round(tolerance * tolerance_multiplier))
    window_seconds = max(_safe_int(settings.get("limiter_window_seconds"), 1800), 1)
    cooldown_seconds = max(_safe_int(settings.get("limiter_cooldown_seconds"), 900), 0)
    ignore_ttl_seconds = max(_safe_int(settings.get("limiter_ignore_ttl_seconds"), 0), 0)

    window_row = conn.execute(
        """
        SELECT event_count, window_started_at
        FROM limiter_state_windows
        WHERE scope_key = ?
        """,
        (scope_key,),
    ).fetchone()
    event_count = 0
    window_started_at = now
    if window_row:
        raw_started = str(window_row["window_started_at"] or "").strip()
        try:
            window_started_at = datetime.fromisoformat(raw_started) if raw_started else now
        except ValueError:
            window_started_at = now
        if (now - window_started_at).total_seconds() <= window_seconds:
            event_count = max(_safe_int(window_row["event_count"], 0), 0)
        else:
            event_count = 0
            window_started_at = now
    event_count += 1

    conn.execute(
        """
        INSERT INTO limiter_state_windows (scope_key, event_count, window_started_at, last_event_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(scope_key) DO UPDATE SET
            event_count = excluded.event_count,
            window_started_at = excluded.window_started_at,
            last_event_at = excluded.last_event_at,
            updated_at = excluded.updated_at
        """,
        (scope_key, event_count, window_started_at.isoformat(), now_iso, now_iso),
    )

    if event_count < threshold:
        return LimiterDecision(False, "below_threshold", scope_key, event_count, threshold, False, None, rollout_mode)

    cooldown_row = conn.execute(
        """
        SELECT cooldown_until
        FROM limiter_state_cooldowns
        WHERE scope_key = ? AND action = ?
        """,
        (scope_key, action),
    ).fetchone()
    cooldown_until = str(cooldown_row["cooldown_until"] or "").strip() if cooldown_row else ""
    cooldown_active = bool(cooldown_until and cooldown_until > now_iso)
    if cooldown_active:
        return LimiterDecision(
            False,
            "cooldown_active",
            scope_key,
            event_count,
            threshold,
            True,
            cooldown_until,
            rollout_mode,
        )

    next_cooldown_until = (now + timedelta(seconds=cooldown_seconds)).isoformat()
    conn.execute(
        """
        INSERT INTO limiter_state_cooldowns (scope_key, action, cooldown_until, last_triggered_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(scope_key, action) DO UPDATE SET
            cooldown_until = excluded.cooldown_until,
            last_triggered_at = excluded.last_triggered_at
        """,
        (scope_key, action, next_cooldown_until, now_iso),
    )
    if ignore_ttl_seconds > 0:
        ignore_until = (now + timedelta(seconds=ignore_ttl_seconds)).isoformat()
        conn.execute(
            """
            INSERT INTO limiter_ignore_rules (scope_key, reason, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(scope_key) DO UPDATE SET
                reason = excluded.reason,
                expires_at = excluded.expires_at,
                updated_at = excluded.updated_at
            """,
            (scope_key, "auto_ignore_ttl", ignore_until, now_iso, now_iso),
        )

    if rollout_mode == "observe":
        return LimiterDecision(False, "rollout_observe", scope_key, event_count, threshold, False, None, rollout_mode)
    if rollout_mode == "warning_only":
        return LimiterDecision(False, "rollout_warning_only", scope_key, event_count, threshold, False, None, rollout_mode)
    return LimiterDecision(True, "enforce", scope_key, event_count, threshold, False, None, rollout_mode)
