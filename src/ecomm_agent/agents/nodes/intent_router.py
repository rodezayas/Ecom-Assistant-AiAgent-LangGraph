"""Intent classification node.

Determines whether an incoming message is a product search or a general
question using deterministic vocabulary matching against
:data:`ecomm_agent.core.domain.COMMERCE_TERMS`. No LLM call is involved.
"""

from ecomm_agent.agents.state import AgentState
from ecomm_agent.core.domain import COMMERCE_TERMS
from ecomm_agent.observability.tracing import get_tracer, is_content_recording_enabled
from ecomm_agent.services.guardrails import tokenize

tracer = get_tracer(__name__)


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
    with tracer.start_as_current_span("intent_router") as span:
        tokens = set(tokenize(state.user_message))
        intent = "product_search" if (tokens & COMMERCE_TERMS) else "general_question"
        result = state.model_copy(update={"intent": intent})
        try:
            span.set_attribute("thread_id", state.thread_id)
            span.set_attribute("intent", intent)
            span.set_attribute("token_count", len(tokens))
            if is_content_recording_enabled():
                span.set_attribute("input.value", state.user_message[:2000])
                span.set_attribute("output.value", intent)
        except Exception:
            pass
        return result
