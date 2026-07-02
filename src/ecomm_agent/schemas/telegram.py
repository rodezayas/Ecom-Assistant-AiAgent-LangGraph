from pydantic import BaseModel, Field


class TelegramChat(BaseModel):
    id: int


class TelegramUser(BaseModel):
    id: int | None = None
    username: str | None = None
    first_name: str | None = None


class TelegramMessage(BaseModel):
    message_id: int | None = None
    chat: TelegramChat
    text: str | None = None
    from_user: TelegramUser | None = Field(default=None, alias="from")

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None

    model_config = {"populate_by_name": True}
