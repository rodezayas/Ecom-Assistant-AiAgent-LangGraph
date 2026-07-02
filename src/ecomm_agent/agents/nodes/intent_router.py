from ecomm_agent.agents.state import AgentState
from ecomm_agent.core.domain import COMMERCE_TERMS
from ecomm_agent.services.guardrails import tokenize


def intent_router_node(state: AgentState) -> AgentState:
    tokens = set(tokenize(state.user_message))
    if tokens & COMMERCE_TERMS:
        return state.model_copy(update={"intent": "product_search"})
    return state.model_copy(update={"intent": "general_question"})
