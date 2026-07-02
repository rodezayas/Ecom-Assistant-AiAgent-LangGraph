from fastapi import FastAPI

from ecomm_agent.api.routes.health import router as health_router
from ecomm_agent.api.routes.telegram import router as telegram_router
from ecomm_agent.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router)
    app.include_router(telegram_router)
    return app


app = create_app()
