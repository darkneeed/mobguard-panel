from __future__ import annotations

from typing import Any, Mapping

from .panel_client import (
    DEFAULT_TRAFFIC_LIMIT_STRATEGY,
    get_full_access_squad_name,
    get_restricted_access_squad_name,
    get_traffic_cap_increment_gb,
    get_traffic_cap_threshold_gb,
)

GIBIBYTE = 1024 ** 3
SQUAD_RESTRICTION_MODE = "SQUAD"
TRAFFIC_CAP_RESTRICTION_MODE = "TRAFFIC_CAP"


def normalize_restriction_mode(value: Any) -> str:
    if str(value or "").upper() == TRAFFIC_CAP_RESTRICTION_MODE:
        return TRAFFIC_CAP_RESTRICTION_MODE
    return SQUAD_RESTRICTION_MODE


def remote_access_squad_name(
    raw_settings: Mapping[str, Any] | None,
    *,
    restricted: bool,
) -> str:
    if restricted:
        return get_restricted_access_squad_name(raw_settings)
    return get_full_access_squad_name(raw_settings)


def apply_remote_access_state(
    client: Any,
    uuid: str,
    raw_settings: Mapping[str, Any] | None,
    *,
    restricted: bool,
) -> bool:
    return bool(
        client.apply_access_squad(
            uuid,
            remote_access_squad_name(raw_settings, restricted=restricted),
        )
    )


async def apply_remote_access_state_async(
    client: Any,
    uuid: str,
    raw_settings: Mapping[str, Any] | None,
    *,
    restricted: bool,
) -> bool:
    return bool(
        await client.apply_access_squad(
            uuid,
            remote_access_squad_name(raw_settings, restricted=restricted),
        )
    )


def traffic_cap_bytes(gigabytes: int) -> int:
    return int(gigabytes) * GIBIBYTE


def _coerce_non_negative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def panel_user_traffic_snapshot(panel_user: Mapping[str, Any] | None) -> dict[str, Any]:
    user = panel_user or {}
    user_traffic = user.get("userTraffic") if isinstance(user.get("userTraffic"), Mapping) else {}
    traffic_limit_strategy = str(
        user.get("trafficLimitStrategy") or DEFAULT_TRAFFIC_LIMIT_STRATEGY
    ).strip() or DEFAULT_TRAFFIC_LIMIT_STRATEGY
    return {
        "traffic_limit_bytes": _coerce_non_negative_int(user.get("trafficLimitBytes")) or 0,
        "traffic_limit_strategy": traffic_limit_strategy,
        "used_traffic_bytes": _coerce_non_negative_int(user_traffic.get("usedTrafficBytes")),
        "lifetime_used_traffic_bytes": _coerce_non_negative_int(
            user_traffic.get("lifetimeUsedTrafficBytes")
        ),
    }


def build_traffic_cap_plan(
    panel_user: Mapping[str, Any] | None,
    gigabytes: int,
) -> dict[str, Any]:
    snapshot = panel_user_traffic_snapshot(panel_user)
    used_traffic_bytes = snapshot["used_traffic_bytes"]
    if used_traffic_bytes is None:
        raise ValueError("usedTrafficBytes is unavailable")

    current_limit_bytes = snapshot["traffic_limit_bytes"]
    traffic_limit_strategy = snapshot["traffic_limit_strategy"]
    target_limit_bytes = used_traffic_bytes + traffic_cap_bytes(gigabytes)
    stricter_existing_limit = current_limit_bytes > 0 and current_limit_bytes <= target_limit_bytes

    if stricter_existing_limit:
        return {
            "restriction_mode": TRAFFIC_CAP_RESTRICTION_MODE,
            "used_traffic_bytes": used_traffic_bytes,
            "lifetime_used_traffic_bytes": snapshot["lifetime_used_traffic_bytes"],
            "target_limit_bytes": target_limit_bytes,
            "saved_traffic_limit_bytes": None,
            "saved_traffic_limit_strategy": None,
            "applied_traffic_limit_bytes": current_limit_bytes,
            "traffic_limit_strategy": traffic_limit_strategy,
            "remote_change_required": False,
            "preserved_existing_limit": True,
        }

    return {
        "restriction_mode": TRAFFIC_CAP_RESTRICTION_MODE,
        "used_traffic_bytes": used_traffic_bytes,
        "lifetime_used_traffic_bytes": snapshot["lifetime_used_traffic_bytes"],
        "target_limit_bytes": target_limit_bytes,
        "saved_traffic_limit_bytes": current_limit_bytes,
        "saved_traffic_limit_strategy": traffic_limit_strategy,
        "applied_traffic_limit_bytes": target_limit_bytes,
        "traffic_limit_strategy": traffic_limit_strategy,
        "remote_change_required": True,
        "preserved_existing_limit": False,
    }


def should_use_traffic_cap(
    panel_user: Mapping[str, Any] | None,
    raw_settings: Mapping[str, Any] | None,
) -> bool:
    used_traffic_bytes = panel_user_traffic_snapshot(panel_user)["used_traffic_bytes"]
    if used_traffic_bytes is None:
        return False
    return used_traffic_bytes >= traffic_cap_bytes(get_traffic_cap_threshold_gb(raw_settings))


def build_auto_restriction_state(
    panel_user: Mapping[str, Any] | None,
    raw_settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if should_use_traffic_cap(panel_user, raw_settings):
        return build_traffic_cap_plan(panel_user, get_traffic_cap_increment_gb(raw_settings))
    return {
        "restriction_mode": SQUAD_RESTRICTION_MODE,
        "saved_traffic_limit_bytes": None,
        "saved_traffic_limit_strategy": None,
        "applied_traffic_limit_bytes": None,
        "traffic_limit_strategy": None,
        "remote_change_required": True,
        "preserved_existing_limit": False,
        "used_traffic_bytes": panel_user_traffic_snapshot(panel_user)["used_traffic_bytes"],
        "lifetime_used_traffic_bytes": panel_user_traffic_snapshot(panel_user)["lifetime_used_traffic_bytes"],
    }


def apply_remote_traffic_cap(
    client: Any,
    uuid: str,
    panel_user: Mapping[str, Any] | None,
    gigabytes: int,
) -> dict[str, Any]:
    plan = build_traffic_cap_plan(panel_user, gigabytes)
    if not plan["remote_change_required"]:
        return {**plan, "remote_updated": True, "remote_changed": False}
    remote_updated = bool(
        client.update_user_traffic_limit(
            uuid,
            plan["applied_traffic_limit_bytes"],
            plan["traffic_limit_strategy"],
        )
    )
    return {
        **plan,
        "remote_updated": remote_updated,
        "remote_changed": remote_updated,
    }


async def apply_remote_traffic_cap_async(
    client: Any,
    uuid: str,
    panel_user: Mapping[str, Any] | None,
    gigabytes: int,
) -> dict[str, Any]:
    plan = build_traffic_cap_plan(panel_user, gigabytes)
    if not plan["remote_change_required"]:
        return {**plan, "remote_updated": True, "remote_changed": False}
    remote_updated = bool(
        await client.update_user_traffic_limit(
            uuid,
            plan["applied_traffic_limit_bytes"],
            plan["traffic_limit_strategy"],
        )
    )
    return {
        **plan,
        "remote_updated": remote_updated,
        "remote_changed": remote_updated,
    }


def apply_remote_restriction_state(
    client: Any,
    uuid: str,
    raw_settings: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None,
) -> bool:
    restriction_mode = normalize_restriction_mode((state or {}).get("restriction_mode"))
    if restriction_mode == TRAFFIC_CAP_RESTRICTION_MODE:
        if (state or {}).get("saved_traffic_limit_bytes") is None:
            return True
        applied_traffic_limit_bytes = _coerce_non_negative_int((state or {}).get("applied_traffic_limit_bytes"))
        if applied_traffic_limit_bytes is None:
            return True
        strategy = str(
            (state or {}).get("saved_traffic_limit_strategy") or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        ).strip() or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        return bool(client.update_user_traffic_limit(uuid, applied_traffic_limit_bytes, strategy))
    return apply_remote_access_state(client, uuid, raw_settings, restricted=True)


async def apply_remote_restriction_state_async(
    client: Any,
    uuid: str,
    raw_settings: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None,
) -> bool:
    restriction_mode = normalize_restriction_mode((state or {}).get("restriction_mode"))
    if restriction_mode == TRAFFIC_CAP_RESTRICTION_MODE:
        if (state or {}).get("saved_traffic_limit_bytes") is None:
            return True
        applied_traffic_limit_bytes = _coerce_non_negative_int((state or {}).get("applied_traffic_limit_bytes"))
        if applied_traffic_limit_bytes is None:
            return True
        strategy = str(
            (state or {}).get("saved_traffic_limit_strategy") or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        ).strip() or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        return bool(await client.update_user_traffic_limit(uuid, applied_traffic_limit_bytes, strategy))
    return await apply_remote_access_state_async(client, uuid, raw_settings, restricted=True)


def restore_remote_restriction_state(
    client: Any,
    uuid: str,
    raw_settings: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    restriction_mode = normalize_restriction_mode((state or {}).get("restriction_mode"))
    if restriction_mode == TRAFFIC_CAP_RESTRICTION_MODE:
        saved_limit_bytes = _coerce_non_negative_int((state or {}).get("saved_traffic_limit_bytes"))
        if saved_limit_bytes is None:
            return {"remote_updated": True, "remote_changed": False}
        strategy = str(
            (state or {}).get("saved_traffic_limit_strategy") or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        ).strip() or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        remote_updated = bool(client.update_user_traffic_limit(uuid, saved_limit_bytes, strategy))
        return {"remote_updated": remote_updated, "remote_changed": remote_updated}
    remote_updated = apply_remote_access_state(client, uuid, raw_settings, restricted=False)
    return {"remote_updated": remote_updated, "remote_changed": remote_updated}


async def restore_remote_restriction_state_async(
    client: Any,
    uuid: str,
    raw_settings: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    restriction_mode = normalize_restriction_mode((state or {}).get("restriction_mode"))
    if restriction_mode == TRAFFIC_CAP_RESTRICTION_MODE:
        saved_limit_bytes = _coerce_non_negative_int((state or {}).get("saved_traffic_limit_bytes"))
        if saved_limit_bytes is None:
            return {"remote_updated": True, "remote_changed": False}
        strategy = str(
            (state or {}).get("saved_traffic_limit_strategy") or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        ).strip() or DEFAULT_TRAFFIC_LIMIT_STRATEGY
        remote_updated = bool(await client.update_user_traffic_limit(uuid, saved_limit_bytes, strategy))
        return {"remote_updated": remote_updated, "remote_changed": remote_updated}
    remote_updated = await apply_remote_access_state_async(client, uuid, raw_settings, restricted=False)
    return {"remote_updated": remote_updated, "remote_changed": remote_updated}
