from ecomm_agent.agents.state import AgentState
from ecomm_agent.core.config import settings
from ecomm_agent.services.catalog import load_catalog
from ecomm_agent.services.guardrails import (
    build_allowed_vocabulary,
    evaluate_message_guardrails,
)


CATALOG = load_catalog(settings.catalog_path)
ALLOWED_VOCABULARY = build_allowed_vocabulary(CATALOG)


def guardrails_node(state: AgentState) -> AgentState:
    result = evaluate_message_guardrails(
        text=state.user_message,
        allowed_vocabulary=ALLOWED_VOCABULARY,
    )
    if result.allowed:
        return state.model_copy(
            update={
                "guardrail_blocked": False,
                "guardrail_reason": None,
                "blocked_terms": [],
            }
        )

    return state.model_copy(
        update={
            "guardrail_blocked": True,
            "guardrail_reason": result.reason,
            "blocked_terms": list(result.matched_terms),
            "intent": "out_of_domain" if result.reason == "out_of_scope" else state.intent,
        }
    )
