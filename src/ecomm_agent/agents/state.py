"""LangGraph agent state.

Defines the typed state passed between LangGraph nodes. Each field documents
which node(s) populate it so the contract of the conversation flow stays
explicit.
"""

from typing import Literal

from pydantic import BaseModel, Field

from ecomm_agent.schemas.catalog import Product


# The three intent buckets the agent can land in. The intent router emits
# ``product_search`` or ``general_question``, and the guardrail node can
# override the intent to ``out_of_domain`` when a message is out of scope.
IntentType = Literal["product_search", "general_question", "out_of_domain"]


class KnowledgeSnippet(BaseModel):
    """A single verified knowledge-base hit.

    Used for general questions answered from the Markdown knowledge base
    (policies, FAQ, size guide). The content always comes from source-of-truth
    documents, never from the LLM.
    """

    source_type: str
    """Document source type: ``policy``, ``faq``, or ``size_guide``."""

    category: str
    """Metadata category the document was indexed under."""

    section: str | None = None
    """Markdown section slug the snippet was extracted from, when applicable."""

    content: str
    """The verified text retrieved for this snippet."""


class AgentState(BaseModel):
    """State object threaded through the LangGraph conversation flow.

    Populated across nodes:

    - ``intent_router`` writes :attr:`intent`.
    - ``retrieval`` writes the requested filters, retrieved products/knowledge,
      and :attr:`retrieval_reason`.
    - ``guardrails`` writes the guardrail flags and may override :attr:`intent`.
    - ``response_generator`` / ``fallback`` write :attr:`response_text`.
    """

    thread_id: str
    """Per-conversation identifier; the Telegram ``chat.id`` in production."""

    user_message: str
    """The raw message text sent by the user."""

    intent: IntentType | None = None
    """Classified intent of the message, set by the intent router."""

    requested_category: str | None = None
    """Category extracted from the message (e.g. ``shoes``), when present."""

    requested_color: str | None = None
    """Color extracted from the message, when present."""

    requested_size: str | None = None
    """Size extracted from the message (normalized to S/M/L/XL), when present."""

    price_ceiling: float | None = None
    """Maximum price extracted from the message, when present."""

    retrieved_products: list[Product] = Field(default_factory=list)
    """Verified products matching the request, filled by the retrieval node."""

    retrieved_knowledge: list[KnowledgeSnippet] = Field(default_factory=list)
    """Verified knowledge-base snippets, filled by the retrieval node."""

    retrieval_reason: str | None = None
    """Why retrieval produced no results (``no_results``), when applicable."""

    guardrail_blocked: bool = False
    """True when the guardrail layer blocked the message."""

    guardrail_reason: str | None = None
    """Guardrail trigger: ``prompt_injection`` or ``out_of_scope``."""

    blocked_terms: list[str] = Field(default_factory=list)
    """Specific terms/phrases that triggered the guardrail."""

    response_text: str | None = None
    """Deterministic reply text written by the response generator or fallback."""
