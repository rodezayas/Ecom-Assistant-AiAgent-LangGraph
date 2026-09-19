"""Pydantic models for Telegram webhook payloads.

Subset of the Telegram Bot API update schema needed by this project. Fields
use snake_case in Python and map back to Telegram's camelCase field names
via aliases.
"""

from pydantic import BaseModel, Field


class TelegramChat(BaseModel):
    """Minimal chat descriptor extracted from a Telegram update."""

    id: int
    """Telegram chat identifier; used as the conversation ``thread_id``."""


class TelegramUser(BaseModel):
    """Minimal sender descriptor extracted from a Telegram update."""

    id: int | None = None
    """Telegram user identifier."""

    username: str | None = None
    """Public username of the sender, when available."""

    first_name: str | None = None
    """First name of the sender, when available."""


class TelegramMessage(BaseModel):
    """A message inside a Telegram update."""

    message_id: int | None = None
    """Telegram identifier of the message."""

    chat: TelegramChat
    """Chat the message was sent in."""

    text: str | None = Field(default=None, max_length=4000)
    """Message text; ``None`` for non-text messages (e.g. photos). Truncated at 4000 chars."""

    from_user: TelegramUser | None = Field(default=None, alias="from")
    """Sender of the message (``from`` in the Telegram API)."""

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    """Top-level Telegram update envelope posted to the webhook."""

    update_id: int
    """Monotonically increasing update identifier assigned by Telegram."""

    message: TelegramMessage | None = None
    """The incoming message, when the update carries one."""

    model_config = {"populate_by_name": True}
