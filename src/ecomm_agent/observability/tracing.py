"""Arize Phoenix tracing setup (OTLP/HTTP + OpenInference).

Configures OpenTelemetry to export to Arize Phoenix Cloud via OTLP/HTTP
and auto-instruments LangGraph/LangChain via OpenInference.

Usage is gated by settings.phoenix_enabled and settings.phoenix_api_key:
when disabled the module is a no-op so the app runs without Phoenix.
"""

from __future__ import annotations

import logging

from ecomm_agent.core.config import settings

logger = logging.getLogger(__name__)

_TRACING_CONFIGURED = False


def _get_phoenix_headers() -> dict[str, str] | None:
    """Build Phoenix Cloud headers.

    Phoenix Cloud expects api_key authentication.
    Returns None when no key is configured.
    """
    if settings.phoenix_api_key:
        return {"api_key": settings.phoenix_api_key}
    return None


def setup_tracing() -> bool:
    """Configure Phoenix tracing via OTLP/HTTP and LangChain instrumentation.

    Reads from global settings (phoenix_enabled, phoenix_collector_endpoint,
    phoenix_project_name, phoenix_api_key, otel_service_name).

    Returns:
        True when tracing was configured, False otherwise (disabled or failed).
    """
    global _TRACING_CONFIGURED
    if _TRACING_CONFIGURED:
        return True

    if not settings.phoenix_enabled:
        logger.info("phoenix tracing disabled (PHOENIX_ENABLED=false)")
        return False

    headers = _get_phoenix_headers()
    if not headers:
        logger.warning(
            "phoenix tracing enabled but PHOENIX_API_KEY is missing; "
            "traces will not be authenticated with Phoenix Cloud"
        )

    try:
        from phoenix.otel import register
    except ImportError as exc:
        logger.warning("phoenix.otel not installed; tracing disabled", extra={"error": str(exc)})
        return False

    try:
        register(
            project_name=settings.phoenix_project_name,
            endpoint=settings.phoenix_collector_endpoint,
            headers=headers,
            auto_instrument=True,
            batch=True,
        )
        logger.info(
            "phoenix tracing registered",
            extra={
                "project": settings.phoenix_project_name,
                "endpoint": settings.phoenix_collector_endpoint,
                "service": settings.otel_service_name,
            },
        )
    except Exception as exc:
        logger.warning("phoenix register failed; continuing without tracing", extra={"error": str(exc)})
        return False

    # Auto-instrument LangGraph/LangChain for chain/node spans.
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor

        LangChainInstrumentor().instrument()
        logger.info("langchain instrumentor enabled")
    except ImportError as exc:
        logger.warning(
            "openinference-instrumentation-langchain not installed; LangGraph auto-tracing disabled",
            extra={"error": str(exc)},
        )
    except Exception as exc:
        logger.warning("langchain instrumentor failed", extra={"error": str(exc)})

    _TRACING_CONFIGURED = True
    return True


def get_tracer(name: str):
    """Return an OpenTelemetry tracer for manual spans.

    Falls back to a no-op tracer when OTEL is not installed.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:

        class _NoOpSpan:
            def set_attribute(self, *_, **__):  # noqa: ANN002, ANN003
                pass

            def set_status(self, *_, **__):  # noqa: ANN002, ANN003
                pass

            def record_exception(self, *_, **__):  # noqa: ANN002, ANN003
                pass

        class _NoOpSpanContext:
            def __enter__(self):  # noqa: ANN204
                return _NoOpSpan()

            def __exit__(self, *_, **__):  # noqa: ANN002, ANN003
                return False

        class _NoOpTracer:
            def start_as_current_span(self, *_, **__):  # noqa: ANN002, ANN003
                return _NoOpSpanContext()

        return _NoOpTracer()


def is_content_recording_enabled() -> bool:
    """Whether input.value/output.value should be recorded in spans."""
    return bool(settings.phoenix_enabled and settings.phoenix_record_content)
