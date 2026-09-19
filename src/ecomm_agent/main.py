"""FastAPI application entry point.

Creates the FastAPI app, configures CORS for the frontend, registers the
catalog/health/telegram routers, and (in the lifespan) configures logging and
registers the Telegram webhook when the required settings are present.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ecomm_agent.api.routes.catalog import router as catalog_router
from ecomm_agent.api.routes.golden import router as golden_router
from ecomm_agent.api.routes.health import router as health_router
from ecomm_agent.api.routes.telegram import router as telegram_router
from ecomm_agent.core.config import settings
from ecomm_agent.observability.logging import configure_logging
from ecomm_agent.services.telegram import set_webhook

# Module-level logger for startup, webhook, and lifecycle messages.
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup/shutdown lifecycle.

    Configures logging on startup and registers the Telegram webhook at
    ``{TELEGRAM_WEBHOOK_PUBLIC_URL}/webhook/telegram`` when both the bot token
    and the public URL are configured. Logs a warning when the token is set
    but the public URL is missing.
    """
    configure_logging()

    # Phoenix Cloud tracing (OTLP/HTTP) — no-op when PHOENIX_ENABLED=false.
    try:
        from ecomm_agent.observability.tracing import setup_tracing

        setup_tracing()
    except Exception as exc:
        logger.warning("phoenix tracing setup failed", extra={"error": str(exc)})

    if settings.telegram_bot_token and settings.telegram_webhook_public_url:
        public_url = settings.telegram_webhook_public_url.rstrip("/")
        # Enforce HTTPS for webhook in production
        if settings.environment == "production" and not public_url.startswith("https://"):
            logger.warning(
                "TELEGRAM_WEBHOOK_PUBLIC_URL must be https in production; webhook not registered",
                extra={"webhook_url": public_url},
            )
        else:
            webhook_url = f"{public_url}/webhook/telegram"
            try:
                await set_webhook(webhook_url)
                # Never log secret token; only base URL
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
    """Build and configure the FastAPI application.

    Registers CORS for the allowed frontend origins and mounts the catalog,
    health, and Telegram routers.

    Returns:
        The configured :class:`FastAPI` application.
    """
    is_prod = settings.environment == "production"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_origin_regex=settings.cors_allowed_origin_regex,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Telegram-Bot-Api-Secret-Token"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if is_prod:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(429)
    async def rate_limit_handler(request: Request, exc):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded, try again later"})

    app.include_router(catalog_router)
    app.include_router(health_router)
    app.include_router(telegram_router)
    app.include_router(golden_router)
    return app


app = create_app()
"""Module-level FastAPI application instance used by the ASGI server."""
