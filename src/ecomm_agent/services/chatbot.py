from ecomm_agent.agents.state import AgentState
from ecomm_agent.core.config import settings
from ecomm_agent.services.catalog import load_catalog
from ecomm_agent.services.guardrails import (
    build_allowed_vocabulary,
    evaluate_message_guardrails,
)


CATALOG = load_catalog(settings.catalog_path)
ALLOWED_VOCABULARY = build_allowed_vocabulary(CATALOG)


def process_user_message(thread_id: str, text: str) -> AgentState:
    state = AgentState(thread_id=thread_id, user_message=text)
    result = evaluate_message_guardrails(text=text, allowed_vocabulary=ALLOWED_VOCABULARY)

    if result.allowed:
        return state.model_copy(
            update={
                "intent": "product_search",
                "response_text": "Request received. In the next phase this message will be connected to real catalog retrieval.",
            }
        )

    if result.reason == "prompt_injection":
        message = (
            "I cannot follow instructions that try to override my internal rules. "
            "I can only help with products, prices, sizes, colors, and verified catalog stock."
        )
    else:
        message = (
            "I can only help with Nova Style clothing, shoes, and accessories. "
            "Ask about products, prices, sizes, colors, or availability."
        )

    return state.model_copy(
        update={
            "intent": "out_of_domain" if result.reason == "out_of_scope" else "general_question",
            "guardrail_blocked": True,
            "guardrail_reason": result.reason,
            "blocked_terms": list(result.matched_terms),
            "response_text": message,
        }
    )
