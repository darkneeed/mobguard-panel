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
ADMIN_REASON_MAX_LINES = 4
ADMIN_REASON_OMIT_PREFIXES = (
    "[analysis]",
    "querying ipinfo",
    "ipinfo/runtime asn result",
    "hostname:",
    "asn classification",
)


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
        event: str | None = None,
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
                topic_id=self._topic_for_admin_event(raw_settings, event),
            )
        )
        return True

    async def notify_admin_force(
        self,
        text: str,
        *,
        chat_id_override: str | None = None,
        topic_id_override: int | None = None,
        dedupe_key: str | None = None,
    ) -> bool:
        raw_settings = self._settings()
        env_values = self._env_values()
        token = str(env_values.get("TG_ADMIN_BOT_TOKEN") or "").strip()
        chat_id = str(chat_id_override or raw_settings.get("tg_admin_chat_id") or "").strip()
        if not token or not chat_id:
            return False
        if dedupe_key and self._is_deduped(f"admin-force:{dedupe_key}"):
            return False
        await self._queue.put(
            _QueuedTelegramMessage(
                token=token,
                chat_id=chat_id,
                text=text,
                topic_id=topic_id_override
                if topic_id_override is not None
                else _coerce_topic_id(raw_settings.get("tg_topic_id")),
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
        logger.info("Sending Telegram notification to user %s (event: %s): %s", telegram_id, event, text)
        try:
            self.container.store.record_admin_audit_event(
                actor_subject="system",
                actor_role="system",
                actor_auth_method="system",
                actor_telegram_id=None,
                actor_username="system",
                action="telegram.notification.user",
                target_type="user",
                target_id=str(telegram_id),
                details={"event": event, "text": text, "dry_run": dry_run},
            )
        except Exception:
            logger.exception("Failed to write Telegram notification audit log")

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

    def _topic_for_admin_event(self, raw_settings: Mapping[str, Any], event: str | None) -> int | None:
        if event:
            with self.container.store._connect() as conn:
                if self.container.store._table_exists(conn, "telegram_topic_routing"):
                    row = conn.execute(
                        "SELECT topic_id FROM telegram_topic_routing WHERE event_key = ?",
                        (str(event),),
                    ).fetchone()
                    if row:
                        topic = _coerce_topic_id(row["topic_id"])
                        if topic is not None:
                            return topic
            event_key = f"tg_topic_{event}"
            topic = _coerce_topic_id(raw_settings.get(event_key))
            if topic is not None:
                return topic
            route_key = f"telegram_topic_route_{event}"
            route_topic = _coerce_topic_id(raw_settings.get(route_key))
            if route_topic is not None:
                return route_topic
        return _coerce_topic_id(raw_settings.get("tg_topic_id"))


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


def _compact_admin_reason_lines(raw_lines: list[Any]) -> list[str]:
    compact: list[str] = []
    seen: set[str] = set()
    for item in raw_lines:
        text = " ".join(str(item or "").split())
        if not text:
            continue
        lowered = text.lower()
        if any(lowered.startswith(prefix) for prefix in ADMIN_REASON_OMIT_PREFIXES):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        compact.append(escape_html(text))
        if len(compact) >= ADMIN_REASON_MAX_LINES:
            break
    return compact


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
            await _notify_enforcement(
                notifier,
                container,
                user,
                bundle,
                tag,
                enforcement,
                review_reason=review_reason,
            )
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
    if str(detail.get("status") or "").upper() != "OPEN":
        return
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
    from mobguard_platform.usage_profile import determine_risk_title
    risk_title = determine_risk_title(usage_profile, bundle)
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
            "risk_title": risk_title,
            **build_usage_profile_template_context(usage_profile),
        },
    )
    message = message.replace("РИСК ПРОФИЛЯ ИСПОЛЬЗОВАНИЯ", risk_title)
    message = message.replace("Риск профиля использования", risk_title)
    message = message.replace("риск профиля использования", risk_title)
    if bundle.case_id:
        message += f"\n<b>Case ID:</b> <code>{int(bundle.case_id)}</code>\n"
    dedupe_key = (
        f"review-case:{int(bundle.case_id)}"
        if bundle.case_id not in (None, "")
        else f"review:{user.get('uuid')}:{bundle.ip}:{review_reason}"
    )
    await notifier.notify_admin(
        message,
        event="review",
        dedupe_key=dedupe_key,
    )


async def _notify_enforcement(
    notifier: TelegramNotifier,
    container: Any,
    user: Mapping[str, Any],
    bundle: Any,
    tag: str,
    enforcement: Mapping[str, Any],
    *,
    review_reason: str | None = None,
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
    from mobguard_platform.usage_profile import determine_risk_title
    risk_title = determine_risk_title(usage_profile, bundle)
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
        "risk_title": risk_title,
        **build_usage_profile_template_context(usage_profile),
    }
    admin_message = ""
    user_message = ""
    user_event = ""
    enforcement_type = str(enforcement.get("type") or "")
    is_warning_only = bool(enforcement.get("warning_only"))
    if enforcement_type == "warning":
        if bool(enforcement.get("warning_only")):
            if not review_reason and admin_event_enabled(raw_settings, "warning_only", has_admin_bot=has_admin_bot):
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
    elif enforcement_type == "ban":
        if admin_event_enabled(raw_settings, "ban", has_admin_bot=has_admin_bot):
            admin_message = render_telegram_template(raw_settings, "admin_ban_template", common_context)
        user_event = "ban"
        user_message = render_telegram_template(raw_settings, "user_ban_template", common_context)

    if admin_message:
        admin_message = admin_message.replace("РИСК ПРОФИЛЯ ИСПОЛЬЗОВАНИЯ", risk_title)
        admin_message = admin_message.replace("Риск профиля использования", risk_title)
        admin_message = admin_message.replace("риск профиля использования", risk_title)
        if enforcement_type == "warning" and is_warning_only and bundle.case_id not in (None, ""):
            admin_dedupe_key = f"enforcement-warning-case:{int(bundle.case_id)}"
        else:
            admin_dedupe_key = f"enforcement:{bundle.event_id}:{enforcement_type}:{is_warning_only}"
        await notifier.notify_admin(
            admin_message,
            event=(
                "warning_only"
                if enforcement_type == "warning" and is_warning_only
                else "warning"
                if enforcement_type == "warning"
                else "ban"
            ),
            dedupe_key=admin_dedupe_key,
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
