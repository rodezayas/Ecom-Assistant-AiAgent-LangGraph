"""Telegram webhook route.

Receives Telegram updates, runs them through the agent graph, builds the reply
text, and sends it back to the originating chat. Includes webhook secret
verification, rate limiting, replay dedup, and production-safe response
minimization.
"""

import logging
import time
from collections import deque

from fastapi import APIRouter, Depends, Request, status

from ecomm_agent.api.security import check_rate_limit, verify_telegram_secret
from ecomm_agent.core.config import settings
from ecomm_agent.observability.tracing import get_tracer, is_content_recording_enabled
from ecomm_agent.schemas.telegram import TelegramUpdate
from ecomm_agent.services.chatbot import build_reply_text, process_user_message
from ecomm_agent.services.telegram import send_text_message

# Telegram webhook endpoint; receives updates and replies to the originating chat.
router = APIRouter(prefix="/webhook", tags=["telegram"])
logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

# Replay protection: remember recent update_ids for 10 minutes.
_seen_updates: deque[tuple[int, float]] = deque(maxlen=10000)


def _is_duplicate_update(update_id: int) -> bool:
    now = time.monotonic()
    # Evict older than 600s
    while _seen_updates and _seen_updates[0][1] < now - 600:
        _seen_updates.popleft()
    for uid, _ in _seen_updates:
        if uid == update_id:
            return True
    _seen_updates.append((update_id, now))
    return False


def clear_seen_updates() -> None:
    """Clear replay dedup cache (used in tests)."""
    _seen_updates.clear()


@router.post("/telegram", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    request: Request,
    update: TelegramUpdate,
    _auth: None = Depends(verify_telegram_secret),
) -> dict[str, str | int | bool | list[str] | None]:
    """Process a Telegram update and reply to the chat.

    Args:
        request: FastAPI request for rate limiting.
        update: The Telegram update payload.
        _auth: Dependency that verifies the webhook secret token.

    Returns:
        A dict reporting the outcome: thread id, guardrail status, response
        text, whether the Telegram reply was sent, and any Telegram error.
        In production ``ENVIRONMENT=production`` verbose fields are minimized.
    """
    # Rate limit per-IP
    check_rate_limit(request, settings.rate_limit_webhook_per_minute)

    # Replay protection
    if _is_duplicate_update(update.update_id):
        return {
            "status": "accepted",
            "thread_id": "0",
            "guardrail_blocked": False,
            "guardrail_reason": "",
            "blocked_terms": [],
            "response_text": "",
            "telegram_sent": False,
            "telegram_message_id": None,
            "telegram_error": None,
        }

    with tracer.start_as_current_span("webhook.telegram") as span:
        chat_id = update.message.chat.id if update.message else None
        raw_text = update.message.text if update.message and update.message.text else ""
        # Enforce max length (Pydantic already caps, but truncate defensively)
        text = raw_text[: settings.max_telegram_text_length] if raw_text else ""
        try:
            span.set_attribute("thread_id", str(chat_id or 0))
            span.set_attribute("http.route", "/webhook/telegram")
            if is_content_recording_enabled() and text:
                span.set_attribute("input.value", text[:2000])
        except Exception:
            pass
        if not chat_id or not text.strip():
            try:
                span.set_attribute("webhook.empty", True)
            except Exception:
                pass
            return {
                "status": "accepted",
                "thread_id": str(chat_id or 0),
                "guardrail_blocked": False,
                "guardrail_reason": "",
                "blocked_terms": [],
                "response_text": "",
                "telegram_sent": False,
                "telegram_message_id": None,
                "telegram_error": None,
            }

        state = process_user_message(thread_id=str(chat_id or 0), text=text)
        try:
            span.set_attribute("intent", state.intent or "")
            span.set_attribute("guardrail.blocked", state.guardrail_blocked)
            span.set_attribute("guardrail.reason", state.guardrail_reason or "")
        except Exception:
            pass
        response_text = await build_reply_text(state)
        try:
            if is_content_recording_enabled():
                span.set_attribute("output.value", response_text[:4000])
            span.set_attribute("response.length", len(response_text))
        except Exception:
            pass
        try:
            telegram_result = await send_text_message(chat_id=chat_id, text=response_text)
        except Exception as exc:
            logger.exception(
                "failed to send Telegram reply",
                extra={"chat_id": chat_id},
            )
            try:
                span.record_exception(exc)
                span.set_attribute("telegram.sent", False)
            except Exception:
                pass
            # In production minimize verbose error output
            if settings.environment == "production":
                return {
                    "status": "accepted",
                    "thread_id": str(chat_id or 0),
                    "guardrail_blocked": state.guardrail_blocked,
                    "guardrail_reason": state.guardrail_reason or "",
                    "blocked_terms": [],
                    "response_text": "",
                    "telegram_sent": False,
                    "telegram_message_id": None,
                    "telegram_error": None,
                }
            return {
                "status": "accepted",
                "thread_id": str(chat_id or 0),
                "guardrail_blocked": state.guardrail_blocked,
                "guardrail_reason": state.guardrail_reason or "",
                "blocked_terms": state.blocked_terms,
                "response_text": response_text,
                "telegram_sent": False,
                "telegram_message_id": None,
                "telegram_error": "telegram send failed",
            }

        telegram_ok = bool(telegram_result.get("ok")) if isinstance(telegram_result, dict) else False
        telegram_message = telegram_result.get("result", {}) if isinstance(telegram_result, dict) else {}
        telegram_description = (
            telegram_result.get("description", "")
            if isinstance(telegram_result, dict)
            else ""
        )
        try:
            span.set_attribute("telegram.sent", telegram_ok)
            if telegram_message.get("message_id"):
                span.set_attribute("telegram.message_id", telegram_message.get("message_id"))
        except Exception:
            pass

        # Production: minimize verbose fields that aid reconnaissance
        if settings.environment == "production":
            return {
                "status": "accepted",
                "thread_id": str(chat_id or 0),
                "guardrail_blocked": state.guardrail_blocked,
                "guardrail_reason": state.guardrail_reason or "",
                "blocked_terms": [],
                "response_text": "",
                "telegram_sent": telegram_ok,
                "telegram_message_id": telegram_message.get("message_id"),
                "telegram_error": None,
            }

        return {
            "status": "accepted",
            "thread_id": str(chat_id or 0),
            "guardrail_blocked": state.guardrail_blocked,
            "guardrail_reason": state.guardrail_reason or "",
            "blocked_terms": state.blocked_terms,
            "response_text": response_text,
            "telegram_sent": telegram_ok,
            "telegram_message_id": telegram_message.get("message_id"),
            "telegram_error": telegram_description or None,
        }
