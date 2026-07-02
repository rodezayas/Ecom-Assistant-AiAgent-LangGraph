from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from ecomm_agent.api.routes.health import router as health_router
from ecomm_agent.api.routes.telegram import router as telegram_router
from ecomm_agent.core.config import settings
from ecomm_agent.observability.logging import configure_logging
from ecomm_agent.services.telegram import set_webhook

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()

    if settings.telegram_bot_token and settings.telegram_webhook_public_url:
        webhook_url = (
            f"{settings.telegram_webhook_public_url.rstrip('/')}/webhook/telegram"
        )
        try:
            await set_webhook(webhook_url)
            logger.info("telegram webhook registered", extra={"webhook_url": webhook_url})
        except Exception as exc:
            logger.exception(
                "telegram webhook registration failed",
                extra={"webhook_url": webhook_url, "error": str(exc)},
            )
    elif settings.telegram_bot_token and not settings.telegram_webhook_public_url:
        logger.warning(
            "telegram bot token is set but TELEGRAM_WEBHOOK_PUBLIC_URL is missing; "
            "Telegram messages will not reach this FastAPI app"
        )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(telegram_router)
    return app


app = create_app()
