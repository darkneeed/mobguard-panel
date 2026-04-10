from __future__ import annotations

from fastapi import FastAPI

from .context import build_container
from .routers.auth import router as auth_router
from .routers.data_admin import router as data_admin_router
from .routers.health import router as health_router
from .routers.metrics import router as metrics_router
from .routers.reviews import router as reviews_router
from .routers.settings import router as settings_router


container = build_container()


def create_app() -> FastAPI:
    app = FastAPI(title="MobGuard Admin API", version="1.1.0")
    app.state.container = container
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(reviews_router)
    app.include_router(settings_router)
    app.include_router(data_admin_router)
    app.include_router(metrics_router)
    return app


app = create_app()
