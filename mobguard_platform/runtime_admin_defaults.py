from __future__ import annotations

from typing import Any, Mapping

from .panel_client import (
    DEFAULT_FULL_ACCESS_SQUAD_NAME,
    DEFAULT_RESTRICTED_ACCESS_SQUAD_NAME,
    DEFAULT_TRAFFIC_CAP_INCREMENT_GB,
    DEFAULT_TRAFFIC_CAP_THRESHOLD_GB,
)


ENFORCEMENT_SETTINGS_DEFAULTS = {
    "usage_time_threshold": 900,
    "warning_timeout_seconds": 900,
    "warnings_before_ban": 3,
    "ban_durations_minutes": [15, 60, 1440, 20160],
    "warning_only_mode": False,
    "manual_review_mixed_home_enabled": False,
    "manual_ban_approval_enabled": False,
    "dry_run": True,
    "report_time": "06:00",
    "full_access_squad_name": DEFAULT_FULL_ACCESS_SQUAD_NAME,
    "restricted_access_squad_name": DEFAULT_RESTRICTED_ACCESS_SQUAD_NAME,
    "traffic_cap_increment_gb": DEFAULT_TRAFFIC_CAP_INCREMENT_GB,
    "traffic_cap_threshold_gb": DEFAULT_TRAFFIC_CAP_THRESHOLD_GB,
}


TELEGRAM_RUNTIME_SETTINGS_DEFAULTS = {
    "tg_admin_chat_id": "",
    "tg_topic_id": 0,
    "telegram_message_min_interval_seconds": 1.0,
    "telegram_admin_notifications_enabled": True,
    "telegram_user_notifications_enabled": True,
    "telegram_admin_commands_enabled": True,
    "telegram_notify_admin_review_enabled": True,
    "telegram_notify_admin_warning_only_enabled": True,
    "telegram_notify_admin_warning_enabled": True,
    "telegram_notify_admin_ban_enabled": True,
    "telegram_notify_user_warning_only_enabled": True,
    "telegram_notify_user_warning_enabled": True,
    "telegram_notify_user_ban_enabled": True,
}


TELEGRAM_NOTIFICATION_LEGACY_FALLBACKS = {
    "telegram_notify_admin_review_enabled": "telegram_notify_review_enabled",
    "telegram_notify_admin_warning_only_enabled": "telegram_notify_warning_only_enabled",
    "telegram_notify_admin_warning_enabled": "telegram_notify_warning_enabled",
    "telegram_notify_admin_ban_enabled": "telegram_notify_ban_enabled",
    "telegram_notify_user_warning_only_enabled": "telegram_notify_warning_only_enabled",
    "telegram_notify_user_warning_enabled": "telegram_notify_warning_enabled",
    "telegram_notify_user_ban_enabled": "telegram_notify_ban_enabled",
}


TELEGRAM_EVENT_SETTING_KEYS = {
    ("admin", "review"): "telegram_notify_admin_review_enabled",
    ("admin", "warning_only"): "telegram_notify_admin_warning_only_enabled",
    ("admin", "warning"): "telegram_notify_admin_warning_enabled",
    ("admin", "ban"): "telegram_notify_admin_ban_enabled",
    ("user", "warning_only"): "telegram_notify_user_warning_only_enabled",
    ("user", "warning"): "telegram_notify_user_warning_enabled",
    ("user", "ban"): "telegram_notify_user_ban_enabled",
}


def normalize_telegram_runtime_settings(raw_settings: Mapping[str, Any] | None) -> dict[str, Any]:
    source = raw_settings or {}
    normalized: dict[str, Any] = {}

    for key, default in TELEGRAM_RUNTIME_SETTINGS_DEFAULTS.items():
        if key in source:
            normalized[key] = source[key]
            continue

        legacy_key = TELEGRAM_NOTIFICATION_LEGACY_FALLBACKS.get(key)
        if legacy_key and legacy_key in source:
            normalized[key] = source[legacy_key]
            continue

        normalized[key] = default

    return normalized


def telegram_notification_setting(
    raw_settings: Mapping[str, Any] | None,
    key: str,
) -> bool:
    normalized = normalize_telegram_runtime_settings(raw_settings)
    return bool(normalized.get(key, TELEGRAM_RUNTIME_SETTINGS_DEFAULTS[key]))


def telegram_event_notifications_enabled(
    raw_settings: Mapping[str, Any] | None,
    recipient: str,
    event: str,
) -> bool:
    master_key = f"telegram_{recipient}_notifications_enabled"
    if not telegram_notification_setting(raw_settings, master_key):
        return False

    event_key = TELEGRAM_EVENT_SETTING_KEYS[(recipient, event)]
    return telegram_notification_setting(raw_settings, event_key)


ENFORCEMENT_TEMPLATE_DEFAULTS = {
    "user_warning_only_template": (
        "⚠️ <b>Предупреждение</b>\n\n"
        "Система обнаружила спорные признаки использования конфига <b>«Мобильный интернет»</b> "
        "через не-мобильную сеть.\n"
        "Доступ сейчас не ограничивается, но кейс отправлен на модерацию.\n\n"
        "📱 Пожалуйста, используйте эту конфигурацию только через мобильный интернет.\n"
    ),
    "user_warning_template": (
        "⚠️ <b>Предупреждение</b>\n\n"
        "Система анализа выявила признаки использования конфига <b>«Мобильный интернет»</b> "
        "через не-мобильную сеть.\n"
        "Это запрещено пунктом 6 правил пользования, <b>доступ к части серверов может быть ограничен.</b>\n\n"
        "📱 Пожалуйста, используйте эту конфигурацию только через мобильный интернет.\n"
    ),
    "user_ban_template": (
        "⛔️ <b>Доступ ограничен</b>\n\n"
        "Вы не отреагировали на предупреждение и продолжили использование конфигурации "
        "<b>«Мобильный интернет»</b> через не-мобильную сеть.\n\n"
        "⏳ <b>Ограничение на {{ban_text}}.</b>\n"
        "Полный доступ восстановится автоматически по истечении срока ограничения."
    ),
    "admin_warning_only_template": (
        "📶 <b>#mobguard</b>\n"
        "➖➖➖➖➖➖➖➖➖\n"
        "⚠️ <b>ПРЕДУПРЕЖДЕНИЕ БЕЗ ЭСКАЛАЦИИ</b>\n"
        "<b>Username:</b> {{username}}\n"
        "<b>System ID:</b> {{system_id}}\n"
        "<b>Telegram ID:</b> {{telegram_id}}\n"
        "<b>UUID:</b> {{uuid}}\n"
        "<b>IP:</b> <code>{{ip}}</code>\n"
        "<b>ISP:</b> {{isp}}\n"
        "<b>Config:</b> {{tag}}\n"
        "<b>Причина:</b> {{confidence_band}} / punitive disabled\n"
        "<b>Review URL:</b> <code>{{review_url}}</code>\n"
    ),
    "admin_warning_template": (
        "📶 <b>#mobguard</b>\n"
        "➖➖➖➖➖➖➖➖➖\n"
        "⚠️ <b>ПРЕДУПРЕЖДЕНИЕ {{warning_count}}/{{warnings_before_ban}}</b>\n"
        "<b>Username:</b> {{username}}\n"
        "<b>System ID:</b> {{system_id}}\n"
        "<b>Telegram ID:</b> {{telegram_id}}\n"
        "<b>UUID:</b> {{uuid}}\n"
        "<b>IP:</b> <code>{{ip}}</code>\n"
        "<b>ISP:</b> {{isp}}\n"
        "<b>Config:</b> {{tag}}\n"
        "<b>Left:</b> {{warnings_left}}\n"
        "<b>Review URL:</b> <code>{{review_url}}</code>\n"
    ),
    "admin_ban_template": (
        "📶 <b>#mobguard</b>\n"
        "➖➖➖➖➖➖➖➖➖\n"
        "⛔️ <b>ОГРАНИЧЕНИЕ ДОСТУПА</b>\n"
        "<b>Username:</b> {{username}}\n"
        "<b>System ID:</b> {{system_id}}\n"
        "<b>Telegram ID:</b> {{telegram_id}}\n"
        "<b>UUID:</b> {{uuid}}\n"
        "<b>IP:</b> <code>{{ip}}</code>\n"
        "<b>ISP:</b> {{isp}}\n"
        "<b>Config:</b> {{tag}}\n"
        "<b>Warning count:</b> {{warning_count}}\n"
        "<b>Restriction:</b> {{ban_minutes}} мин ({{ban_text}})\n"
        "<b>Review URL:</b> <code>{{review_url}}</code>\n"
    ),
    "admin_review_template": (
        "📶 <b>#mobguard</b>\n"
        "➖➖➖➖➖➖➖➖➖\n"
        "🔍 <b>ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА</b>\n"
        "<b>Username:</b> {{username}}\n"
        "<b>System ID:</b> {{system_id}}\n"
        "<b>Telegram ID:</b> {{telegram_id}}\n"
        "<b>UUID:</b> {{uuid}}\n"
        "<b>IP:</b> <code>{{ip}}</code>\n"
        "<b>ISP:</b> {{isp}}\n"
        "<b>Config:</b> {{tag}}\n"
        "<b>Verdict:</b> {{confidence_band}}\n"
        "<b>Review URL:</b> <code>{{review_url}}</code>\n"
    ),
}
