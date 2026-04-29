from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping

import aiohttp

from mobguard_platform.runtime_admin_defaults import ENFORCEMENT_SETTINGS_DEFAULTS
from mobguard_platform.telegram_runtime import (
    admin_event_enabled,
    admin_notifications_enabled,
    escape_html,
    format_duration_text,
    render_telegram_template,
    telegram_setting,
    user_event_enabled,
    user_notifications_enabled,
)
from mobguard_platform.usage_profile import (
    build_usage_profile_admin_lines,
    build_usage_profile_snapshot,
    build_usage_profile_template_context,
)

from .runtime_state import load_env_values, load_runtime_config


logger = logging.getLogger(__name__)
TELEGRAM_API_ROOT = "https://api.telegram.org"


@dataclass(slots=True)
class _QueuedTelegramMessage:
    token: str
    chat_id: str
    text: str
    topic_id: int | None = None


class TelegramNotifier:
    def __init__(self, container: Any):
        self.container = container
        self._queue: asyncio.Queue[_QueuedTelegramMessage] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._session: aiohttp.ClientSession | None = None
        self._dedupe_until: dict[str, float] = {}
        self._last_sent_at = 0.0

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._session = aiohttp.ClientSession()
        self._worker = asyncio.create_task(self._run(), name="mobguard-telegram-notifier")

    async def stop(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def notify_admin(
        self,
        text: str,
        *,
        dedupe_key: str | None = None,
    ) -> bool:
        raw_settings = self._settings()
        env_values = self._env_values()
        token = str(env_values.get("TG_ADMIN_BOT_TOKEN") or "").strip()
        chat_id = str(raw_settings.get("tg_admin_chat_id") or "").strip()
        if not admin_notifications_enabled(raw_settings, has_admin_bot=bool(token)):
            return False
        if not token or not chat_id:
            return False
        if dedupe_key and self._is_deduped(f"admin:{dedupe_key}"):
            return False
        await self._queue.put(
            _QueuedTelegramMessage(
                token=token,
                chat_id=chat_id,
                text=text,
                topic_id=_coerce_topic_id(raw_settings.get("tg_topic_id")),
            )
        )
        return True

    async def notify_user(
        self,
        telegram_id: int,
        text: str,
        *,
        event: str,
        dry_run: bool,
        dedupe_key: str | None = None,
    ) -> bool:
        raw_settings = self._settings()
        env_values = self._env_values()
        token = str(env_values.get("TG_MAIN_BOT_TOKEN") or "").strip()
        if dry_run or not user_notifications_enabled(raw_settings, has_user_bot=bool(token)):
            return False
        if not token or not telegram_id:
            return False
        if not user_event_enabled(raw_settings, event, has_user_bot=True):
            return False
        if dedupe_key and self._is_deduped(f"user:{dedupe_key}"):
            return False
        await self._queue.put(
            _QueuedTelegramMessage(
                token=token,
                chat_id=str(int(telegram_id)),
                text=text,
            )
        )
        return True

    async def _run(self) -> None:
        while True:
            message = await self._queue.get()
            try:
                await self._respect_rate_limit()
                await self._send(message)
                self._last_sent_at = time.monotonic()
            except Exception:
                logger.exception("Telegram notifier send failed")

    async def _respect_rate_limit(self) -> None:
        delay = max(float(telegram_setting(self._settings(), "telegram_message_min_interval_seconds") or 0.0), 0.0)
        if delay <= 0:
            return
        elapsed = time.monotonic() - self._last_sent_at
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)

    async def _send(self, message: _QueuedTelegramMessage) -> None:
        if self._session is None:
            raise RuntimeError("Telegram notifier session is not started")
        payload: dict[str, Any] = {
            "chat_id": message.chat_id,
            "text": message.text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if message.topic_id:
            payload["message_thread_id"] = message.topic_id
        url = f"{TELEGRAM_API_ROOT}/bot{message.token}/sendMessage"
        timeout = aiohttp.ClientTimeout(total=20)
        async with self._session.post(url, json=payload, timeout=timeout) as response:
            raw_body = await response.text()
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError:
                body = {"ok": False, "description": raw_body}
            if response.status == 429:
                retry_after = int(((body.get("parameters") or {}).get("retry_after")) or 1)
                await asyncio.sleep(max(retry_after, 1))
                raise RuntimeError(body.get("description") or "Telegram flood control")
            if response.status >= 400 or not body.get("ok"):
                raise RuntimeError(body.get("description") or f"Telegram HTTP {response.status}")

    def _settings(self) -> dict[str, Any]:
        runtime_config = load_runtime_config(self.container)
        settings = runtime_config.get("settings", {})
        return settings if isinstance(settings, dict) else {}

    def _env_values(self) -> dict[str, str]:
        return load_env_values(self.container)

    def _is_deduped(self, key: str, *, ttl_seconds: float = 6 * 3600) -> bool:
        now = time.monotonic()
        expired = [candidate for candidate, deadline in self._dedupe_until.items() if deadline <= now]
        for candidate in expired:
            self._dedupe_until.pop(candidate, None)
        deadline = self._dedupe_until.get(key)
        if deadline and deadline > now:
            return True
        self._dedupe_until[key] = now + ttl_seconds
        return False


def _coerce_topic_id(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed or None


def _runtime_settings(container: Any) -> dict[str, Any]:
    runtime_config = load_runtime_config(container)
    settings = runtime_config.get("settings", {})
    return settings if isinstance(settings, dict) else {}


def _identity_payload(user: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "uuid": user.get("uuid"),
        "username": user.get("username"),
        "system_id": user.get("id"),
        "telegram_id": user.get("telegramId"),
    }


async def emit_ingest_notifications(
    container: Any,
    user: Mapping[str, Any],
    bundle: Any,
    tag: str,
    review_reason: str | None,
    enforcement: Mapping[str, Any] | None,
) -> None:
    notifier = getattr(container, "telegram_notifier", None)
    if notifier is None:
        return
    try:
        if review_reason and bundle.case_id:
            await _notify_review_case(notifier, container, user, bundle, tag, review_reason)
        if enforcement:
            await _notify_enforcement(notifier, container, user, bundle, tag, enforcement)
    except Exception:
        logger.exception("Post-analysis Telegram notification flow failed")


async def _notify_review_case(
    notifier: TelegramNotifier,
    container: Any,
    user: Mapping[str, Any],
    bundle: Any,
    tag: str,
    review_reason: str,
) -> None:
    raw_settings = _runtime_settings(container)
    env_values = load_env_values(container)
    has_admin_bot = bool(env_values.get("TG_ADMIN_BOT_TOKEN"))
    if not (
        admin_event_enabled(raw_settings, "review", has_admin_bot=has_admin_bot)
        or admin_event_enabled(raw_settings, "usage_profile_risk", has_admin_bot=has_admin_bot)
    ):
        return

    detail = await asyncio.to_thread(container.store.get_review_case, int(bundle.case_id))
    usage_profile = detail.get("usage_profile") or build_usage_profile_snapshot(
        container.store,
        _identity_payload(user),
        panel_user=dict(user),
    )
    title = {
        "unsure": "ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА",
        "probable_home": "ПОГРАНИЧНЫЙ HOME КЕЙС",
        "home_requires_review": "HOME КЕЙС ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ",
        "manual_review_mixed_home": "MIXED ASN HOME КЕЙС",
        "provider_conflict": "КОНФЛИКТ ПРОВАЙДЕРА",
    }.get(review_reason, "ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА")
    template_key = (
        "admin_usage_profile_risk_template"
        if admin_event_enabled(raw_settings, "usage_profile_risk", has_admin_bot=has_admin_bot)
        else "admin_review_template"
    )
    message = render_telegram_template(
        raw_settings,
        template_key,
        {
            "username": user.get("username", "N/A"),
            "uuid": user.get("uuid") or "N/A",
            "system_id": user.get("id") or "",
            "telegram_id": user.get("telegramId") or "",
            "ip": bundle.ip,
            "isp": bundle.isp,
            "tag": tag,
            "confidence_band": f"{title} / {bundle.verdict} / {bundle.confidence_band}",
            "review_url": detail.get("review_url") or "",
            **build_usage_profile_template_context(usage_profile),
        },
    )
    if bundle.case_id:
        message += f"\n<b>Case ID:</b> <code>{int(bundle.case_id)}</code>\n"
    usage_lines = build_usage_profile_admin_lines(usage_profile, scenario="usage_profile_risk")
    if usage_lines:
        message += "\n" + "\n".join(usage_lines) + "\n"
    if bundle.log:
        message += "\n<b>Основания:</b>\n"
        for entry in bundle.log:
            message += f"  • {escape_html(entry)}\n"
    await notifier.notify_admin(
        message,
        dedupe_key=f"review:{user.get('uuid')}:{bundle.ip}:{review_reason}",
    )


async def _notify_enforcement(
    notifier: TelegramNotifier,
    container: Any,
    user: Mapping[str, Any],
    bundle: Any,
    tag: str,
    enforcement: Mapping[str, Any],
) -> None:
    raw_settings = _runtime_settings(container)
    env_values = load_env_values(container)
    has_admin_bot = bool(env_values.get("TG_ADMIN_BOT_TOKEN"))
    has_user_bot = bool(env_values.get("TG_MAIN_BOT_TOKEN"))
    dry_run = bool(raw_settings.get("dry_run", ENFORCEMENT_SETTINGS_DEFAULTS["dry_run"]))
    usage_profile = build_usage_profile_snapshot(
        container.store,
        _identity_payload(user),
        panel_user=dict(user),
    )
    common_context = {
        "username": user.get("username", "N/A"),
        "uuid": user.get("uuid") or "N/A",
        "system_id": user.get("id") or "",
        "telegram_id": user.get("telegramId") or "",
        "ip": bundle.ip,
        "isp": bundle.isp,
        "tag": tag,
        "review_url": container.store.build_review_url(int(bundle.case_id)) if bundle.case_id else "",
        "warning_count": int(enforcement.get("warning_count") or 0),
        "warnings_before_ban": int(
            raw_settings.get("warnings_before_ban", ENFORCEMENT_SETTINGS_DEFAULTS["warnings_before_ban"])
        ),
        "warnings_left": max(
            int(raw_settings.get("warnings_before_ban", ENFORCEMENT_SETTINGS_DEFAULTS["warnings_before_ban"]))
            - int(enforcement.get("warning_count") or 0),
            0,
        ),
        "ban_minutes": int(enforcement.get("ban_minutes") or 0),
        "ban_text": format_duration_text(int(enforcement.get("ban_minutes") or 0))
        if int(enforcement.get("ban_minutes") or 0) > 0
        else "",
        "confidence_band": bundle.confidence_band,
        **build_usage_profile_template_context(usage_profile),
    }
    admin_message = ""
    user_message = ""
    user_event = ""
    if str(enforcement.get("type") or "") == "warning":
        if bool(enforcement.get("warning_only")):
            if admin_event_enabled(raw_settings, "warning_only", has_admin_bot=has_admin_bot):
                admin_message = render_telegram_template(raw_settings, "admin_warning_only_template", common_context)
        else:
            if admin_event_enabled(raw_settings, "warning", has_admin_bot=has_admin_bot):
                admin_message = render_telegram_template(raw_settings, "admin_warning_template", common_context)
                user_event = "warning"
        if bool(enforcement.get("warning_only")):
            user_event = "warning_only"
            user_message = render_telegram_template(raw_settings, "user_warning_only_template", common_context)
        else:
            user_message = render_telegram_template(raw_settings, "user_warning_template", common_context)
    elif str(enforcement.get("type") or "") == "ban":
        if admin_event_enabled(raw_settings, "ban", has_admin_bot=has_admin_bot):
            admin_message = render_telegram_template(raw_settings, "admin_ban_template", common_context)
        user_event = "ban"
        user_message = render_telegram_template(raw_settings, "user_ban_template", common_context)

    if admin_message and bundle.log:
        admin_message += "\n<b>Основание:</b>\n"
        for entry in bundle.log:
            admin_message += f"  • {escape_html(entry)}\n"
    if admin_message:
        await notifier.notify_admin(
            admin_message,
            dedupe_key=f"enforcement:{bundle.event_id}:{enforcement.get('type')}:{enforcement.get('warning_only')}",
        )
    telegram_id = user.get("telegramId")
    if not dry_run and user_message and telegram_id not in (None, "") and has_user_bot:
        try:
            numeric_telegram_id = int(telegram_id)
        except (TypeError, ValueError):
            return
        await notifier.notify_user(
            numeric_telegram_id,
            user_message,
            event=user_event,
            dry_run=dry_run,
            dedupe_key=f"enforcement:{bundle.event_id}:{user_event}:{numeric_telegram_id}",
        )
