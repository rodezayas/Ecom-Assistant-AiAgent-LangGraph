from typing import Literal

from pydantic import BaseModel, Field

from ecomm_agent.schemas.catalog import Product


IntentType = Literal["product_search", "order_status", "general_question", "out_of_domain"]


class AgentState(BaseModel):
    thread_id: str
    user_message: str
    intent: IntentType | None = None
    retrieved_products: list[Product] = Field(default_factory=list)
    guardrail_blocked: bool = False
    guardrail_reason: str | None = None
    blocked_terms: list[str] = Field(default_factory=list)
    response_text: str | None = None
