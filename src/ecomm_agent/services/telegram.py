from __future__ import annotations

import httpx

from ecomm_agent.core.config import settings


async def send_text_message(chat_id: int, text: str) -> dict:
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

    return response.json()


async def set_webhook(webhook_url: str) -> dict:
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


async def get_webhook_info() -> dict:
    if not settings.telegram_bot_token:
        raise RuntimeError("telegram_bot_token is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{settings.telegram_api_base_url.rstrip('/')}/bot{settings.telegram_bot_token}/getWebhookInfo",
        )
        response.raise_for_status()

    return response.json()
