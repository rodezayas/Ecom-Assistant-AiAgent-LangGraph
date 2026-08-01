"""Intent classification node.

Determines whether an incoming message is a product search or a general
question using deterministic vocabulary matching against
:data:`ecomm_agent.core.domain.COMMERCE_TERMS`. No LLM call is involved.
"""

from ecomm_agent.agents.state import AgentState
from ecomm_agent.core.domain import COMMERCE_TERMS
from ecomm_agent.services.guardrails import tokenize


def intent_router_node(state: AgentState) -> AgentState:
    """Classify the user message into an intent.

    If any token of the message appears in the fixed commerce vocabulary the
    message is treated as a product search; otherwise it is a general
    question.

    Args:
        state: Agent state containing ``user_message``.

    Returns:
        A copy of the state with ``intent`` set to ``product_search`` or
        ``general_question``.
    """
    tokens = set(tokenize(state.user_message))
    if tokens & COMMERCE_TERMS:
        return state.model_copy(update={"intent": "product_search"})
    return state.model_copy(update={"intent": "general_question"})
