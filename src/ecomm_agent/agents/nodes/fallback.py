from ecomm_agent.agents.state import AgentState


def fallback_node(state: AgentState) -> AgentState:
    if state.guardrail_blocked:
        if state.guardrail_reason == "prompt_injection":
            message = (
                "I cannot follow instructions that try to override my rules. "
                "I can only use verified Nova Style catalog data."
            )
        else:
            message = (
                "I can only help with Nova Style catalog questions. "
                "Ask about products, prices, sizes, colors, or stock."
            )
    elif state.intent != "product_search":
        message = (
            "I currently support Nova Style products, shipping, returns, payments, "
            "and size guidance. Try asking about those topics directly."
        )
    elif state.retrieval_reason == "catalog_unavailable":
        message = "The catalog is not available right now, so I cannot verify products or stock."
    else:
        message = (
            "I could not find a verified catalog match for that request. "
            "Try a broader query with category, color, size, or budget."
        )

    return state.model_copy(update={"response_text": message})
