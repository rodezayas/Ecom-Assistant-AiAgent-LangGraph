"""Fallback node.

Produces an honest deterministic reply when the conversation cannot be
completed normally: guardrail-blocked messages, searches with no verified
results, or an unavailable catalog. The fallback never fabricates products,
prices, or stock.
"""

from ecomm_agent.agents.state import AgentState


def fallback_node(state: AgentState) -> AgentState:
    """Build a safe, honest fallback reply for the current state.

    Args:
        state: Agent state that was blocked by guardrails or produced no
            verified retrieval results.

    Returns:
        A copy of the state with ``response_text`` set to the appropriate
        fallback message.
    """
    if state.guardrail_blocked:
        if state.guardrail_reason == "prompt_injection":
            message = (
                "I cannot follow instructions that try to override my rules. "
                "I can only use verified Alta Norma Fashion catalog data."
            )
        else:
            message = (
                "I can only help with Alta Norma Fashion catalog questions. "
                "Ask about products, prices, sizes, colors, or stock."
            )
    elif state.intent != "product_search":
        message = (
            "I currently support Alta Norma Fashion products, shipping, returns, payments, "
            "and size guidance. Try asking about those topics directly."
        )
    else:
        message = (
            "I could not find a verified catalog match for that request. "
            "Try a broader query with category, color, size, or budget."
        )

    return state.model_copy(update={"response_text": message})
