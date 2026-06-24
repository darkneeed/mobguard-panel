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
    "traffic_burst_min_bytes": 10737418240,
    "traffic_burst_window_minutes": 60,
    "manual_review_mixed_home_enabled": False,
    "manual_ban_approval_enabled": False,
    "dry_run": False,
    "report_time": "06:00",
    "full_access_squad_name": DEFAULT_FULL_ACCESS_SQUAD_NAME,
    "restricted_access_squad_name": DEFAULT_RESTRICTED_ACCESS_SQUAD_NAME,
    "traffic_cap_increment_gb": DEFAULT_TRAFFIC_CAP_INCREMENT_GB,
    "traffic_cap_threshold_gb": DEFAULT_TRAFFIC_CAP_THRESHOLD_GB,
    "limiter_enabled": False,
    "limiter_threshold_count": 3,
    "limiter_window_seconds": 1800,
    "limiter_cooldown_seconds": 900,
    "limiter_tolerance": 0,
    "limiter_tolerance_multiplier": 1.0,
    "limiter_ignore_ttl_seconds": 0,
    "limiter_group_by_subnet": True,
    "limiter_group_by_asn": True,
    "limiter_rollout_mode": "observe",
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
    "telegram_notify_admin_usage_profile_risk_enabled": True,
    "telegram_notify_admin_violation_continues_enabled": True,
    "telegram_notify_admin_traffic_limit_exceeded_enabled": True,
    "telegram_notify_user_warning_only_enabled": True,
    "telegram_notify_user_warning_enabled": True,
    "telegram_notify_user_ban_enabled": True,
    "tg_topic_review": 0,
    "tg_topic_warning_only": 0,
    "tg_topic_warning": 0,
    "tg_topic_ban": 0,
    "tg_topic_usage_profile_risk": 0,
    "tg_topic_violation_continues": 0,
    "tg_topic_traffic_limit_exceeded": 0,
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
    ("admin", "usage_profile_risk"): "telegram_notify_admin_usage_profile_risk_enabled",
    ("admin", "violation_continues"): "telegram_notify_admin_violation_continues_enabled",
    ("admin", "traffic_limit_exceeded"): "telegram_notify_admin_traffic_limit_exceeded_enabled",
    ("user", "warning_only"): "telegram_notify_user_warning_only_enabled",
    ("user", "warning"): "telegram_notify_user_warning_enabled",
    ("user", "ban"): "telegram_notify_user_ban_enabled",
}

APPLIED_RUNTIME_NOTIFICATION_KEYS = (
    "telegram_admin_notifications_enabled",
    "telegram_user_notifications_enabled",
    "telegram_admin_commands_enabled",
    "telegram_notify_admin_review_enabled",
    "telegram_notify_admin_warning_only_enabled",
    "telegram_notify_admin_warning_enabled",
    "telegram_notify_admin_ban_enabled",
    "telegram_notify_admin_usage_profile_risk_enabled",
    "telegram_notify_admin_violation_continues_enabled",
    "telegram_notify_admin_traffic_limit_exceeded_enabled",
    "telegram_notify_user_warning_only_enabled",
    "telegram_notify_user_warning_enabled",
    "telegram_notify_user_ban_enabled",
)

APPLIED_RUNTIME_NOTIFICATION_LABELS = {
    "telegram_admin_notifications_enabled": "Уведомления администраторам",
    "telegram_user_notifications_enabled": "Уведомления пользователям",
    "telegram_admin_commands_enabled": "Команды администратора в Telegram",
    "telegram_notify_admin_review_enabled": "Админ-уведомления о ревью",
    "telegram_notify_admin_warning_only_enabled": "Админ-уведомления без эскалации",
    "telegram_notify_admin_warning_enabled": "Админ-уведомления о предупреждениях",
    "telegram_notify_admin_ban_enabled": "Админ-уведомления об ограничениях",
    "telegram_notify_admin_usage_profile_risk_enabled": "Админ-уведомления о риске профиля использования",
    "telegram_notify_admin_violation_continues_enabled": "Админ-уведомления о продолжающемся нарушении",
    "telegram_notify_admin_traffic_limit_exceeded_enabled": "Админ-уведомления об ограничении по трафику",
    "telegram_notify_user_warning_only_enabled": "Пользовательские сообщения без эскалации",
    "telegram_notify_user_warning_enabled": "Пользовательские предупреждения",
    "telegram_notify_user_ban_enabled": "Пользовательские сообщения об ограничении доступа",
}


def _mode_summary(raw_settings: Mapping[str, Any] | None) -> tuple[str, str]:
    settings = raw_settings or {}
    dry_run = bool(settings.get("dry_run", ENFORCEMENT_SETTINGS_DEFAULTS["dry_run"]))
    shadow_mode = bool(settings.get("shadow_mode", True))
    warning_only_mode = bool(
        settings.get("warning_only_mode", ENFORCEMENT_SETTINGS_DEFAULTS["warning_only_mode"])
    )
    if dry_run or shadow_mode:
        return ("observe", "Наблюдение")
    if warning_only_mode:
        return ("warning_only", "Реакция: только предупреждения")
    return ("enforce", "Реакция: наказания")


def _bool_label(value: bool) -> str:
    return "включено" if value else "выключено"


def build_applied_runtime_notification(
    previous_settings: Mapping[str, Any] | None,
    current_settings: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    previous = previous_settings or {}
    current = current_settings or {}
    lines: list[str] = []

    previous_mode_key, previous_mode_label = _mode_summary(previous)
    current_mode_key, current_mode_label = _mode_summary(current)
    if previous_mode_key != current_mode_key:
        lines.append(f"• Режим работы: {previous_mode_label} -> {current_mode_label}")

    normalized_previous_telegram = normalize_telegram_runtime_settings(previous)
    normalized_current_telegram = normalize_telegram_runtime_settings(current)
    for key in APPLIED_RUNTIME_NOTIFICATION_KEYS:
        previous_value = bool(normalized_previous_telegram.get(key, TELEGRAM_RUNTIME_SETTINGS_DEFAULTS[key]))
        current_value = bool(normalized_current_telegram.get(key, TELEGRAM_RUNTIME_SETTINGS_DEFAULTS[key]))
        if previous_value == current_value:
            continue
        label = APPLIED_RUNTIME_NOTIFICATION_LABELS.get(key, key)
        lines.append(f"• {label}: {_bool_label(previous_value)} -> {_bool_label(current_value)}")

    if not lines:
        return None

    previous_admin_enabled = bool(
        normalized_previous_telegram.get("telegram_admin_notifications_enabled", True)
    )
    current_admin_enabled = bool(
        normalized_current_telegram.get("telegram_admin_notifications_enabled", True)
    )
    return {
        "message": (
            "📶 <b>#mobguard</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "⚙️ <b>Конфиг применён</b>\n\n"
            + "\n".join(lines)
        ),
        "force_send": previous_admin_enabled and not current_admin_enabled,
        "admin_notifications_enabled": current_admin_enabled,
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
        "📱 Пожалуйста, используйте эту конфигурацию только через мобильный интернет.\n\n"
        "Номер обращения: #{{case_id}}"
    ),
    "user_warning_template": (
        "⚠️ <b>Предупреждение</b>\n\n"
        "Система анализа выявила признаки использования конфига <b>«Мобильный интернет»</b> "
        "через не-мобильную сеть.\n"
        "Это запрещено пунктом 6 правил пользования, <b>доступ к части серверов может быть ограничен.</b>\n\n"
        "📱 Пожалуйста, используйте эту конфигурацию только через мобильный интернет.\n\n"
        "Номер обращения: #{{case_id}}"
    ),
    "user_ban_template": (
        "⛔️ <b>Доступ ограничен</b>\n\n"
        "Вы не отреагировали на предупреждение и продолжили использование конфигурации "
        "<b>«Мобильный интернет»</b> через не-мобильную сеть.\n\n"
        "⏳ <b>Ограничение на {{ban_text}}.</b>\n"
        "Полный доступ восстановится автоматически по истечении срока ограничения.\n\n"
        "Номер обращения: #{{case_id}}"
    ),

    "user_warning_only_devices_template": (
        "⚠️ <b>Предупреждение: Лимит устройств</b>\n\n"
        "Система обнаружила превышение лимита одновременно подключенных устройств на вашем аккаунте.\n"
        "Доступ сейчас не ограничивается, но кейс отправлен на модерацию.\n\n"
        "📱 Пожалуйста, соблюдайте лимит устройств: <b>{{usage_profile_hwid_device_limit}}</b> (подключено: <b>{{usage_profile_hwid_device_count_exact}}</b>).\n\n"
        "Номер обращения: #{{case_id}}"
    ),
    "user_warning_only_traffic_template": (
        "⚠️ <b>Предупреждение: Высокий трафик</b>\n\n"
        "Система обнаружила всплеск трафика или превышение лимита на вашем аккаунте.\n"
        "Доступ сейчас не ограничивается, но кейс отправлен на модерацию.\n\n"
        "📊 Использовано за интервал: <b>{{usage_profile_traffic_burst_bytes}}</b> за <b>{{usage_profile_traffic_burst_window}} мин</b>.\n\n"
        "Номер обращения: #{{case_id}}"
    ),
    "user_warning_devices_template": (
        "⚠️ <b>Предупреждение: Превышение лимита устройств</b>\n\n"
        "Система выявила превышение лимита одновременно подключенных устройств на вашем аккаунте.\n"
        "Это нарушает правила использования, <b>доступ к части серверов может быть ограничен.</b>\n\n"
        "📱 Пожалуйста, отключите лишние устройства. Лимит: <b>{{usage_profile_hwid_device_limit}}</b> (подключено: <b>{{usage_profile_hwid_device_count_exact}}</b>).\n\n"
        "Номер обращения: #{{case_id}}"
    ),
    "user_warning_traffic_template": (
        "⚠️ <b>Предупреждение: Превышение трафика</b>\n\n"
        "Система выявила критический всплеск трафика на вашем аккаунте.\n"
        "Это нарушает правила использования, <b>доступ к части серверов может быть ограничен.</b>\n\n"
        "📊 Использовано: <b>{{usage_profile_traffic_burst_bytes}}</b> за <b>{{usage_profile_traffic_burst_window}} мин</b>.\n\n"
        "Номер обращения: #{{case_id}}"
    ),
    "user_ban_devices_template": (
        "⛔️ <b>Доступ ограничен: Превышение лимита устройств</b>\n\n"
        "Вы не отреагировали на предупреждение и продолжили превышать лимит подключенных устройств.\n\n"
        "⏳ <b>Ограничение на {{ban_text}}.</b>\n"
        "Лимит: <b>{{usage_profile_hwid_device_limit}}</b> (подключено: <b>{{usage_profile_hwid_device_count_exact}}</b>).\n\n"
        "Полный доступ восстановится автоматически по истечении срока ограничения.\n\n"
        "Номер обращения: #{{case_id}}"
    ),
    "user_ban_traffic_template": (
        "⛔️ <b>Доступ ограничен: Превышение трафика</b>\n\n"
        "Вы не отреагировали на предупреждение и продолжили использовать трафик в объёмах, нарушающих лимиты.\n\n"
        "⏳ <b>Ограничение на {{ban_text}}.</b>\n"
        "Использовано: <b>{{usage_profile_traffic_burst_bytes}}</b> за <b>{{usage_profile_traffic_burst_window}} мин</b>.\n\n"
        "Полный доступ восстановится автоматически по истечении срока ограничения.\n\n"
        "Номер обращения: #{{case_id}}"
    ),

    # ─── ADMIN TEMPLATES ────────────────────────────────────────────────────────

    "admin_warning_only_template": (
        "⚠️ <b>ПРЕДУПРЕЖДЕНИЕ БЕЗ ЭСКАЛАЦИИ</b>\n\n"
        "👤 <b>{{username}}</b>\n"
        "🆔 ID: {{telegram_id}}\n"
        "📱 Username: @{{username}}\n"
        "🔑 UUID: <code>{{uuid}}</code>\n\n"
        "🚨 <b>Нарушение:</b> {{risk_title}}\n"
        "🔍 <b>Причина:</b> {{confidence_band}}\n"
        "📊 Профиль: {{usage_profile_summary}}\n"
        "🚩 Флаги: {{usage_profile_soft_reasons}}\n\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),
    "admin_warning_template": (
        "⚠️ <b>ПРЕДУПРЕЖДЕНИЕ {{warning_count}}/{{warnings_before_ban}}</b>\n\n"
        "👤 <b>{{username}}</b>\n"
        "🆔 ID: {{telegram_id}}\n"
        "📱 Username: @{{username}}\n"
        "🔑 UUID: <code>{{uuid}}</code>\n\n"
        "🚨 <b>Нарушение:</b> {{risk_title}}\n"
        "🔍 <b>Вердикт:</b> {{confidence_band}}\n"
        "📊 Профиль: {{usage_profile_summary}}\n"
        "🚩 Флаги: {{usage_profile_soft_reasons}}\n\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),
    "admin_ban_template": (
        "⛔️ <b>ОГРАНИЧЕНИЕ ДОСТУПА</b>\n\n"
        "👤 <b>{{username}}</b>\n"
        "🆔 ID: {{telegram_id}}\n"
        "📱 Username: @{{username}}\n"
        "🔑 UUID: <code>{{uuid}}</code>\n\n"
        "🚨 <b>Нарушение:</b> {{risk_title}}\n"
        "⏳ <b>Ограничение:</b> {{ban_text}} ({{ban_minutes}} мин)\n"
        "🔍 <b>Вердикт:</b> {{confidence_band}}\n"
        "📊 Профиль: {{usage_profile_summary}}\n"
        "🚩 Флаги: {{usage_profile_soft_reasons}}\n\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),
    "admin_review_template": (
        "🔍 <b>ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА</b>\n\n"
        "👤 <b>{{username}}</b>\n"
        "🆔 ID: {{telegram_id}}\n"
        "📱 Username: @{{username}}\n"
        "🔑 UUID: <code>{{uuid}}</code>\n\n"
        "🚨 <b>Нарушение:</b> {{risk_title}}\n"
        "🔍 <b>Вердикт:</b> {{confidence_band}}\n"
        "📊 Профиль: {{usage_profile_summary}}\n"
        "🚩 Флаги: {{usage_profile_soft_reasons}}\n\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),

    # ПРЕВЫШЕНИЕ ТРАФИКА — формат как на скриншоте 1
    "admin_usage_profile_traffic_template": (
        "⚠️ <b>Превышение трафика</b>\n\n"
        "👤 {{username}}\n"
        "🆔 ID: {{telegram_id}}\n"
        "📱 Username: @{{username}}\n"
        "🔑 UUID: {{uuid}}\n\n"
        "⚡ <b>Быстрая проверка</b>\n"
        "📊 За интервал: <b>{{usage_profile_traffic_burst_bytes}}</b>\n"
        "📉 Порог: <b>{{usage_profile_traffic_burst_window}} мин</b>\n"
        "🚨 IP: <b>{{usage_profile_ip_count}}</b> | Провайдеры: <b>{{usage_profile_provider_count}}</b>\n\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),

    # ПРЕВЫШЕНИЕ КОЛИЧЕСТВА УСТРОЙСТВ — формат как на скриншоте 2
    "admin_usage_profile_devices_template": (
        "⚠️ <b>Превышение лимита устройств</b>\n\n"
        "👤 Пользователь: {{telegram_id}}\n"
        "🔑 UUID: {{uuid}}\n"
        "📊 Лимит: <b>{{usage_profile_hwid_device_limit}}</b> устройств\n"
        "🔴 Обнаружено: <b>{{usage_profile_hwid_device_count_exact}}</b>\n\n"
        "📱 <b>Устройства:</b>\n"
        "{{usage_profile_device_labels}}\n\n"
        "🖥 <b>Ноды:</b> {{usage_profile_nodes}}\n\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),

    # НЕВЕРНЫЙ ТИП ПОДКЛЮЧЕНИЯ — компактный формат
    "admin_usage_profile_connection_template": (
        "⚠️ <b>Неверный тип подключения</b>\n\n"
        "👤 <b>{{username}}</b>\n"
        "🆔 ID: {{telegram_id}}\n"
        "🔑 UUID: <code>{{uuid}}</code>\n\n"
        "🌐 IP адресов: <b>{{usage_profile_ip_count}}</b>\n"
        "📡 Провайдеров: <b>{{usage_profile_provider_count}}</b>\n"
        "📡 Провайдеры: {{usage_profile_top_providers}}\n"
        "🖥 Ноды: {{usage_profile_nodes}}\n\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),

    # НАРУШЕНИЕ ПРОДОЛЖАЕТСЯ — формат как на скриншоте 3/4
    "admin_violation_continues_template": (
        "⚠️ <b>НАРУШЕНИЕ ПРОДОЛЖАЕТСЯ</b>\n\n"
        "📧 Email: {{system_id}}\n"
        "📱 TG ID: {{telegram_id}}\n"
        "📝 Описание: {{username}}\n\n"
        "🌐 IP адресов: <b>{{usage_profile_ip_count}}/{{usage_profile_provider_count}}</b>\n"
        "📍 IP (провайдеры):\n"
        "{{usage_profile_top_ips}}\n\n"
        "🖥 Ноды: {{usage_profile_nodes}}\n\n"
        "⏱ В нарушении: <b>{{usage_profile_ongoing_duration_text}}</b>\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),

    # НАРУШИТЕЛЬ ЛИМИТА ТРАФИКА (бан по TRAFFIC_CAP)
    "admin_traffic_limit_exceeded_template": (
        "🚫 <b>НАРУШИТЕЛЬ ЛИМИТА ТРАФИКА</b>\n\n"
        "📧 Email: {{system_id}}\n"
        "📱 TG ID: {{telegram_id}}\n"
        "📝 Описание: {{username}}\n\n"
        "🌐 IP адресов: <b>{{usage_profile_ip_count}}/{{usage_profile_provider_count}}</b>\n"
        "📍 IP (провайдеры):\n"
        "{{usage_profile_top_ips}}\n\n"
        "🖥 Ноды: {{usage_profile_nodes}}\n"
        "📱 Устройства ({{usage_profile_hwid_device_count_exact}}):\n"
        "{{usage_profile_device_labels}}\n\n"
        "⏱ В нарушении: <b>{{usage_profile_ongoing_duration_text}}</b>\n"
        "⏰ Ограничение: <b>{{ban_text}}</b>\n"
        "📋 Case ID: <code>{{case_id}}</code>\n"
        "🔗 <a href=\"{{review_url}}\">Открыть кейс</a>\n"
    ),
}

