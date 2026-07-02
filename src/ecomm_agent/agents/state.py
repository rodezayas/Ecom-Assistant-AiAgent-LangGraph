from typing import Literal

from pydantic import BaseModel, Field

from ecomm_agent.schemas.catalog import Product


IntentType = Literal["product_search", "order_status", "general_question", "out_of_domain"]


class KnowledgeSnippet(BaseModel):
    source_type: str
    category: str
    section: str | None = None
    content: str


class AgentState(BaseModel):
    thread_id: str
    user_message: str
    intent: IntentType | None = None
    requested_category: str | None = None
    requested_color: str | None = None
    requested_size: str | None = None
    price_ceiling: float | None = None
    retrieved_products: list[Product] = Field(default_factory=list)
    retrieved_knowledge: list[KnowledgeSnippet] = Field(default_factory=list)
    retrieval_reason: str | None = None
    guardrail_blocked: bool = False
    guardrail_reason: str | None = None
    blocked_terms: list[str] = Field(default_factory=list)
    response_text: str | None = None
