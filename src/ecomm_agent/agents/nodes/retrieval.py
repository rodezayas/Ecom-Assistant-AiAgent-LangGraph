"""Retrieval node.

Executes retrieval for the classified intent: product search queries the
catalog, while general questions query the knowledge base. The extracted
filters (category, color, size, price ceiling) are written back to state so
downstream nodes and the LLM only ever see verified data.
"""

from ecomm_agent.agents.state import AgentState
from ecomm_agent.services.retrieval import retrieve_knowledge, retrieve_products


def retrieval_node(state: AgentState) -> AgentState:
    """Run catalog or knowledge retrieval depending on the intent.

    Args:
        state: Agent state with ``intent`` populated by the intent router.

    Returns:
        A copy of the state with the retrieved products/knowledge and the
        extracted request filters. ``retrieval_reason`` is set to
        ``no_results`` when nothing is found.
    """
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
