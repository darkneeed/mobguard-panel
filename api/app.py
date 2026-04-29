from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .context import build_container
from .logging_console import ensure_console_logging
from .routers.auth import router as auth_router
from .routers.decisions import router as decisions_router
from .routers.data_admin import router as data_admin_router
from .routers.health import router as health_router
from .routers.metrics import router as metrics_router
from .routers.modules import router as modules_router
from .routers.reviews import router as reviews_router
from .routers.settings import router as settings_router
from .services.db_maintenance import db_maintenance_loop
from .services.ingest_pipeline import enforcement_dispatcher_loop, ingest_worker_loop
from .services.telegram_notifier import TelegramNotifier


container = build_container()
ensure_console_logging(container.runtime.db_path, service_name="mobguard-api")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MobGuard API startup complete")
    telegram_notifier = TelegramNotifier(app.state.container)
    setattr(app.state.container, "telegram_notifier", telegram_notifier)
    await telegram_notifier.start()
    maintenance_task = asyncio.create_task(db_maintenance_loop(app.state.container))
    ingest_worker_task = asyncio.create_task(ingest_worker_loop(app.state.container))
    enforcement_dispatcher_task = asyncio.create_task(enforcement_dispatcher_loop(app.state.container))
    try:
        yield
    finally:
        logger.info("MobGuard API shutdown requested")
        maintenance_task.cancel()
        ingest_worker_task.cancel()
        enforcement_dispatcher_task.cancel()
        with suppress(asyncio.CancelledError):
            await maintenance_task
        with suppress(asyncio.CancelledError):
            await ingest_worker_task
        with suppress(asyncio.CancelledError):
            await enforcement_dispatcher_task
        await telegram_notifier.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="MobGuard Admin API", version="1.1.0", lifespan=lifespan)
    app.state.container = container
    app.include_router(health_router)
    app.include_router(modules_router)
    app.include_router(auth_router)
    app.include_router(reviews_router)
    app.include_router(settings_router)
    app.include_router(data_admin_router)
    app.include_router(decisions_router)
    app.include_router(metrics_router)
    return app


app = create_app()
