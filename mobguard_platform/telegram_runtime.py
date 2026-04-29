from __future__ import annotations

from typing import Any, Mapping

from .runtime_admin_defaults import (
    ENFORCEMENT_TEMPLATE_DEFAULTS,
    normalize_telegram_runtime_settings,
    telegram_event_notifications_enabled,
    telegram_notification_setting,
)
from .template_utils import render_optional_template


def escape_html(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_duration_text(minutes: int) -> str:
    if minutes % 10080 == 0:
        weeks = minutes // 10080
        return f"{weeks} нед." if weeks > 1 else "1 неделя"
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} дн." if days > 1 else "24 часа"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} ч." if hours > 1 else "1 час"
    return f"{minutes} мин."


def enforcement_template(raw_settings: Mapping[str, Any] | None, key: str) -> str:
    settings = raw_settings or {}
    return str(settings.get(key, ENFORCEMENT_TEMPLATE_DEFAULTS[key]))


def render_telegram_template(
    raw_settings: Mapping[str, Any] | None,
    template_key: str,
    context: dict[str, Any],
) -> str:
    return render_optional_template(
        enforcement_template(raw_settings, template_key),
        context,
        escape_html,
    )


def telegram_setting(raw_settings: Mapping[str, Any] | None, key: str) -> Any:
    return normalize_telegram_runtime_settings(raw_settings)[key]


def admin_notifications_enabled(
    raw_settings: Mapping[str, Any] | None,
    *,
    has_admin_bot: bool,
) -> bool:
    return bool(has_admin_bot) and telegram_notification_setting(
        raw_settings,
        "telegram_admin_notifications_enabled",
    )


def user_notifications_enabled(
    raw_settings: Mapping[str, Any] | None,
    *,
    has_user_bot: bool,
) -> bool:
    return bool(has_user_bot) and telegram_notification_setting(
        raw_settings,
        "telegram_user_notifications_enabled",
    )


def admin_event_enabled(
    raw_settings: Mapping[str, Any] | None,
    event: str,
    *,
    has_admin_bot: bool,
) -> bool:
    return bool(has_admin_bot) and telegram_event_notifications_enabled(
        raw_settings,
        "admin",
        event,
    )


def user_event_enabled(
    raw_settings: Mapping[str, Any] | None,
    event: str,
    *,
    has_user_bot: bool,
) -> bool:
    return bool(has_user_bot) and telegram_event_notifications_enabled(
        raw_settings,
        "user",
        event,
    )
