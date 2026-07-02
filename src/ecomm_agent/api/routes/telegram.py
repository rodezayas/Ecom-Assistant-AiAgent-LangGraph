from fastapi import APIRouter, status

from ecomm_agent.schemas.telegram import TelegramUpdate
from ecomm_agent.services.chatbot import process_user_message

router = APIRouter(prefix="/webhook", tags=["telegram"])


@router.post("/telegram", status_code=status.HTTP_202_ACCEPTED)
def telegram_webhook(update: TelegramUpdate) -> dict[str, str | int | bool | list[str]]:
    chat_id = update.message.chat.id if update.message else None
    text = update.message.text if update.message and update.message.text else ""
    state = process_user_message(thread_id=str(chat_id or 0), text=text)
    return {
        "status": "accepted",
        "thread_id": str(chat_id or 0),
        "guardrail_blocked": state.guardrail_blocked,
        "guardrail_reason": state.guardrail_reason or "",
        "blocked_terms": state.blocked_terms,
        "response_text": state.response_text or "",
    }
