from __future__ import annotations


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
}


TELEGRAM_RUNTIME_SETTINGS_DEFAULTS = {
    "tg_admin_chat_id": "",
    "tg_topic_id": 0,
    "telegram_message_min_interval_seconds": 1.0,
    "telegram_admin_notifications_enabled": True,
    "telegram_user_notifications_enabled": True,
    "telegram_admin_commands_enabled": True,
    "telegram_notify_review_enabled": True,
    "telegram_notify_warning_only_enabled": True,
    "telegram_notify_warning_enabled": True,
    "telegram_notify_ban_enabled": True,
}


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
        "Это запрещено пунктом 6 правил пользования, <b>доступ к сервису может быть ограничен.</b>\n\n"
        "📱 Пожалуйста, используйте эту конфигурацию только через мобильный интернет.\n"
    ),
    "user_ban_template": (
        "⛔️ <b>Доступ временно ограничен</b>\n\n"
        "Вы не отреагировали на предупреждение и продолжили использование конфигурации "
        "<b>«Мобильный интернет»</b> через не-мобильную сеть.\n\n"
        "⏳ <b>Блокировка на {{ban_text}}.</b>\n"
        "Доступ восстановится автоматически по истечении срока блокировки."
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
        "⛔️ <b>БЛОКИРОВКА</b>\n"
        "<b>Username:</b> {{username}}\n"
        "<b>System ID:</b> {{system_id}}\n"
        "<b>Telegram ID:</b> {{telegram_id}}\n"
        "<b>UUID:</b> {{uuid}}\n"
        "<b>IP:</b> <code>{{ip}}</code>\n"
        "<b>ISP:</b> {{isp}}\n"
        "<b>Config:</b> {{tag}}\n"
        "<b>Warning count:</b> {{warning_count}}\n"
        "<b>Ban:</b> {{ban_minutes}} мин ({{ban_text}})\n"
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
