from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .context import build_container
from .routers.auth import router as auth_router
from .routers.data_admin import router as data_admin_router
from .routers.health import router as health_router
from .routers.metrics import router as metrics_router
from .routers.modules import router as modules_router
from .routers.reviews import router as reviews_router
from .routers.settings import router as settings_router
from .services.db_maintenance import db_maintenance_loop


container = build_container()


@asynccontextmanager
async def lifespan(app: FastAPI):
    maintenance_task = asyncio.create_task(db_maintenance_loop(app.state.container))
    try:
        yield
    finally:
        maintenance_task.cancel()
        with suppress(asyncio.CancelledError):
            await maintenance_task


def create_app() -> FastAPI:
    app = FastAPI(title="MobGuard Admin API", version="1.1.0", lifespan=lifespan)
    app.state.container = container
    app.include_router(health_router)
    app.include_router(modules_router)
    app.include_router(auth_router)
    app.include_router(reviews_router)
    app.include_router(settings_router)
    app.include_router(data_admin_router)
    app.include_router(metrics_router)
    return app


app = create_app()
