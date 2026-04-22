from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..context import APIContainer


logger = logging.getLogger("mobguard.db_maintenance")


def _deleted_total(report: dict[str, Any]) -> int:
    deleted = report.get("deleted", {})
    if not isinstance(deleted, dict):
        return 0
    total = 0
    for value in deleted.values():
        try:
            total += int(value or 0)
        except (TypeError, ValueError):
            continue
    return total


async def run_db_maintenance_once(
    container: APIContainer,
    *,
    mode: str = "periodic",
) -> dict[str, Any]:
    report = await container.store.async_run_db_maintenance(mode=mode)
    if report.get("skipped"):
        logger.info(
            "DB maintenance skipped: mode=%s reason=%s",
            report.get("mode"),
            report.get("skip_reason"),
        )
        return report
    total = _deleted_total(report)
    if total > 0:
        logger.info(
            "DB maintenance completed: mode=%s deleted=%s details=%s",
            report.get("mode"),
            total,
            report.get("deleted"),
        )
    else:
        logger.debug("DB maintenance completed: mode=%s no rows pruned", report.get("mode"))
    return report


async def db_maintenance_loop(container: APIContainer) -> None:
    while True:
        try:
            interval = container.store.get_db_maintenance_settings()["db_cleanup_interval_minutes"]
        except Exception:
            logger.exception("Failed to read db cleanup interval, falling back to 30 minutes")
            interval = 30
        await asyncio.sleep(max(int(interval), 1) * 60)
        try:
            await run_db_maintenance_once(container, mode="periodic")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("DB maintenance pass failed")
