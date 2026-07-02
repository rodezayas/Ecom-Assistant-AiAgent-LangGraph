from ecomm_agent.agents.state import AgentState
from ecomm_agent.services.retrieval import retrieve_knowledge, retrieve_products


def retrieval_node(state: AgentState) -> AgentState:
    retrieval_reason = None

    if state.intent == "product_search":
        (
            products,
            category,
            color,
            size,
            price_ceiling,
        ) = retrieve_products(state.user_message)
        if not products:
            retrieval_reason = "no_results"

        return state.model_copy(
            update={
                "requested_category": category,
                "requested_color": color,
                "requested_size": size,
                "price_ceiling": price_ceiling,
                "retrieved_products": products,
                "retrieved_knowledge": [],
                "retrieval_reason": retrieval_reason,
            }
        )

    knowledge = retrieve_knowledge(state.user_message)
    if not knowledge:
        retrieval_reason = "no_results"

    return state.model_copy(
        update={
            "retrieved_products": [],
            "retrieved_knowledge": knowledge,
            "retrieval_reason": retrieval_reason,
        }
    )
