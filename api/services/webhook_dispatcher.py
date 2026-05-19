from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import aiohttp

from .runtime_state import load_runtime_config


logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _url_allowed(url: str, allowlist_raw: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    allowlist = [item.strip() for item in str(allowlist_raw or "").split(",") if item.strip()]
    if not allowlist:
        return True
    return any(url.startswith(prefix) for prefix in allowlist)


def _signature(secret: str, body: str) -> str:
    payload = body.encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@dataclass(slots=True)
class _WebhookJob:
    event_type: str
    target_url: str
    payload: dict[str, Any]
    secret: str
    timeout_seconds: int
    max_attempts: int
    backoff_seconds: int


class WebhookDispatcher:
    def __init__(self, container: Any):
        self.container = container
        self._queue: asyncio.Queue[_WebhookJob] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._session = aiohttp.ClientSession()
        self._worker = asyncio.create_task(self._run(), name="mobguard-webhook-dispatcher")

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

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        runtime_config = load_runtime_config(self.container)
        settings = runtime_config.get("settings", {})
        if not isinstance(settings, dict) or not bool(settings.get("webhook_enabled", False)):
            return
        urls = [item.strip() for item in str(settings.get("webhook_urls") or "").splitlines() if item.strip()]
        secret = str(settings.get("webhook_secret") or "").strip()
        timeout_seconds = max(_safe_int(settings.get("webhook_timeout_seconds"), 10), 1)
        max_attempts = max(_safe_int(settings.get("webhook_retry_attempts"), 3), 1)
        backoff_seconds = max(_safe_int(settings.get("webhook_backoff_seconds"), 2), 1)
        allowlist_raw = str(settings.get("webhook_allowlist") or "").strip()
        for url in urls:
            if not _url_allowed(url, allowlist_raw):
                logger.warning("Webhook URL rejected by allowlist: %s", url)
                continue
            await self._queue.put(
                _WebhookJob(
                    event_type=event_type,
                    target_url=url,
                    payload=dict(payload),
                    secret=secret,
                    timeout_seconds=timeout_seconds,
                    max_attempts=max_attempts,
                    backoff_seconds=backoff_seconds,
                )
            )

    async def _run(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._dispatch(job)
            except Exception:
                logger.exception("Webhook dispatch failed unexpectedly")

    async def _dispatch(self, job: _WebhookJob) -> None:
        body = json.dumps(job.payload, ensure_ascii=False)
        attempt = 0
        delivery_id = await asyncio.to_thread(
            self._insert_delivery_row,
            job,
            body,
        )
        while attempt < job.max_attempts:
            attempt += 1
            success, response_status, response_body, error_text = await self._send_once(job, body)
            await asyncio.to_thread(
                self._update_delivery_row,
                delivery_id,
                status="delivered" if success else "retrying",
                attempt_count=attempt,
                response_status=response_status,
                response_body=response_body,
                error_text=error_text,
                delivered_at=_utcnow() if success else "",
                next_attempt_at="",
            )
            if success:
                return
            if attempt >= job.max_attempts:
                await asyncio.to_thread(
                    self._update_delivery_row,
                    delivery_id,
                    status="failed",
                    attempt_count=attempt,
                    response_status=response_status,
                    response_body=response_body,
                    error_text=error_text,
                    delivered_at="",
                    next_attempt_at="",
                )
                return
            next_attempt_at = (
                datetime.utcnow().replace(microsecond=0)
                + timedelta(seconds=job.backoff_seconds * attempt)
            ).isoformat()
            await asyncio.to_thread(
                self._update_delivery_row,
                delivery_id,
                status="retrying",
                attempt_count=attempt,
                response_status=response_status,
                response_body=response_body,
                error_text=error_text,
                delivered_at="",
                next_attempt_at=next_attempt_at,
            )
            await asyncio.sleep(job.backoff_seconds * attempt)

    async def _send_once(self, job: _WebhookJob, body: str) -> tuple[bool, int, str, str]:
        if self._session is None:
            return False, 0, "", "webhook session is not started"
        headers = {"Content-Type": "application/json", "X-Webhook-Event": job.event_type}
        if job.secret:
            headers["X-Webhook-Secret"] = _signature(job.secret, body)
        timeout = aiohttp.ClientTimeout(total=job.timeout_seconds)
        try:
            async with self._session.post(job.target_url, data=body.encode("utf-8"), headers=headers, timeout=timeout) as response:
                response_text = await response.text()
                if 200 <= response.status < 300:
                    return True, int(response.status), response_text[:2000], ""
                return False, int(response.status), response_text[:2000], f"HTTP {response.status}"
        except Exception as exc:
            return False, 0, "", str(exc)

    def _insert_delivery_row(self, job: _WebhookJob, body: str) -> int:
        now = _utcnow()
        with self.container.store._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO webhook_deliveries (
                    event_type, target_url, status, attempt_count, response_status, response_body,
                    error_text, delivered_at, next_attempt_at, payload_json, created_at, updated_at
                )
                VALUES (?, ?, 'queued', 0, NULL, '', '', '', '', ?, ?, ?)
                """,
                (job.event_type, job.target_url, body, now, now),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def _update_delivery_row(
        self,
        delivery_id: int,
        *,
        status: str,
        attempt_count: int,
        response_status: int,
        response_body: str,
        error_text: str,
        delivered_at: str,
        next_attempt_at: str,
    ) -> None:
        now = _utcnow()
        with self.container.store._connect() as conn:
            conn.execute(
                """
                UPDATE webhook_deliveries
                SET status = ?,
                    attempt_count = ?,
                    response_status = ?,
                    response_body = ?,
                    error_text = ?,
                    delivered_at = ?,
                    next_attempt_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    attempt_count,
                    response_status or None,
                    response_body[:2000],
                    error_text[:1000],
                    delivered_at,
                    next_attempt_at,
                    now,
                    delivery_id,
                ),
            )
            conn.commit()
