import logging

from fastapi import APIRouter, status

from ecomm_agent.schemas.telegram import TelegramUpdate
from ecomm_agent.services.chatbot import build_reply_text, process_user_message
from ecomm_agent.services.telegram import send_text_message

router = APIRouter(prefix="/webhook", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.post("/telegram", status_code=status.HTTP_202_ACCEPTED)
async def telegram_webhook(
    update: TelegramUpdate,
) -> dict[str, str | int | bool | list[str] | None]:
    chat_id = update.message.chat.id if update.message else None
    text = update.message.text if update.message and update.message.text else ""
    if not chat_id or not text.strip():
        return {
            "status": "accepted",
            "thread_id": str(chat_id or 0),
            "guardrail_blocked": False,
            "guardrail_reason": "",
            "blocked_terms": [],
            "response_text": "",
            "telegram_sent": False,
            "telegram_message_id": None,
        }

    state = process_user_message(thread_id=str(chat_id or 0), text=text)
    response_text = await build_reply_text(state)
    try:
        telegram_result = await send_text_message(chat_id=chat_id, text=response_text)
    except Exception as exc:
        logger.exception(
            "failed to send Telegram reply",
            extra={"chat_id": chat_id, "error": str(exc)},
        )
        return {
            "status": "accepted",
            "thread_id": str(chat_id or 0),
            "guardrail_blocked": state.guardrail_blocked,
            "guardrail_reason": state.guardrail_reason or "",
            "blocked_terms": state.blocked_terms,
            "response_text": response_text,
            "telegram_sent": False,
            "telegram_message_id": None,
            "telegram_error": str(exc),
        }

    telegram_ok = bool(telegram_result.get("ok")) if isinstance(telegram_result, dict) else False
    telegram_message = telegram_result.get("result", {}) if isinstance(telegram_result, dict) else {}
    telegram_description = (
        telegram_result.get("description", "")
        if isinstance(telegram_result, dict)
        else ""
    )

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
