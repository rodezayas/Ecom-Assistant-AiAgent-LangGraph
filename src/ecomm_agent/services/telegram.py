"""Telegram Bot API client.

Thin async wrappers over the Telegram Bot API using ``httpx``: sending
replies and registering the webhook.
"""

from __future__ import annotations

import httpx

from ecomm_agent.core.config import settings
from ecomm_agent.observability.tracing import get_tracer, is_content_recording_enabled

tracer = get_tracer(__name__)


async def send_text_message(chat_id: int, text: str) -> dict:
    """Send a plain-text message to a Telegram chat.

    Args:
        chat_id: Destination chat identifier.
        text: Message body.

    Returns:
        The Telegram API JSON response.

    Raises:
        RuntimeError: When ``TELEGRAM_BOT_TOKEN`` is not configured.
        httpx.HTTPError: When the Telegram API call fails.
    """
    with tracer.start_as_current_span("telegram.sendMessage") as span:
        try:
            span.set_attribute("telegram.chat_id", str(chat_id))
            span.set_attribute("telegram.text_length", len(text))
            if is_content_recording_enabled():
                span.set_attribute("input.value", text[:4000])
        except Exception:
            pass
        if not settings.telegram_bot_token:
            raise RuntimeError("telegram_bot_token is not configured")

        payload = {
            "chat_id": chat_id,
            "text": text,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{settings.telegram_api_base_url.rstrip('/')}/bot{settings.telegram_bot_token}/sendMessage",
                json=payload,
            )
            response.raise_for_status()

        body = response.json()
        try:
            span.set_attribute("telegram.ok", bool(body.get("ok")))
        except Exception:
            pass
        return body


async def set_webhook(webhook_url: str) -> dict:
    """Register the public webhook URL with Telegram.

    Args:
        webhook_url: The full public URL Telegram should POST updates to.

    Returns:
        The Telegram API JSON response.

    Raises:
        RuntimeError: When ``TELEGRAM_BOT_TOKEN`` is not configured.
        httpx.HTTPError: When the Telegram API call fails.
    """
    if not settings.telegram_bot_token:
        raise RuntimeError("telegram_bot_token is not configured")

    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"],
        "drop_pending_updates": False,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.telegram_api_base_url.rstrip('/')}/bot{settings.telegram_bot_token}/setWebhook",
            json=payload,
        )
        response.raise_for_status()

    return response.json()
