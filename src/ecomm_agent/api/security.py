"""Security helpers: webhook auth, admin auth, rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request, status

from ecomm_agent.core.config import settings


# ---------------------------------------------------------------------------
# Telegram webhook secret token
# ---------------------------------------------------------------------------
async def verify_telegram_secret(
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> None:
    """Verify Telegram webhook secret token when configured.

    Telegram sends ``X-Telegram-Bot-Api-Secret-Token`` when ``secret_token``
    was set via ``setWebhook``. If ``TELEGRAM_WEBHOOK_SECRET_TOKEN`` is set in
    environment, we require the header to match; otherwise we allow the request
    (dev mode without secret).
    """
    expected = settings.telegram_webhook_secret_token
    if not expected:
        return
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret token")


# ---------------------------------------------------------------------------
# Admin API key for golden writes/evaluate
# ---------------------------------------------------------------------------
async def verify_admin_key(request: Request) -> None:
    """Require ``Authorization: Bearer <ADMIN_API_KEY>`` when configured."""
    expected = settings.admin_api_key
    if not expected:
        # No key configured → allow (dev). In production set ADMIN_API_KEY.
        return
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin credentials")
    token = auth.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin credentials")


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter (per-IP sliding window)
# ---------------------------------------------------------------------------
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def _is_rate_limited(key: str, limit_per_minute: int) -> bool:
    now = time.monotonic()
    window_start = now - 60.0
    bucket = _rate_buckets[key]
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= limit_per_minute:
        return True
    bucket.append(now)
    return False


def check_rate_limit(request: Request, limit_per_minute: int) -> None:
    """Raise 429 when per-IP rate limit is exceeded."""
    # Use client host if available, fallback to forwarded header.
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    key = f"{request.url.path}:{client_ip}"
    if _is_rate_limited(key, limit_per_minute):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded, try again later")
