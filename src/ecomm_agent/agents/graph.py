"""LangGraph orchestration.

Wires the agent nodes into a compiled graph and defines the conditional
routing between them. The graph topology:

::

    START -> intent_router -> retrieval -> guardrails -> response_generator -> END
                                  |              |
                                  +-> guardrails -> fallback -> END

Intent routing:

- ``product_search`` and ``general_question`` proceed to retrieval.
- Any other intent proceeds directly to guardrails (and then fallback).

Guardrail routing:

- A blocked message always goes to the fallback node.
- A search with no results (products or knowledge) goes to the fallback node.
- Otherwise the message reaches the response generator.
"""

from langgraph.graph import END, START, StateGraph

from ecomm_agent.agents.nodes.fallback import fallback_node
from ecomm_agent.agents.nodes.guardrails import guardrails_node
from ecomm_agent.agents.nodes.intent_router import intent_router_node
from ecomm_agent.agents.nodes.response_generator import response_generator_node
from ecomm_agent.agents.nodes.retrieval import retrieval_node
from ecomm_agent.agents.state import AgentState


def route_after_intent(state: AgentState) -> str:
    """Decide the next node after intent classification.

    Args:
        state: Current agent state with a populated ``intent``.

    Returns:
        ``"retrieval"`` for search and general questions, otherwise
        ``"guardrails"``.
    """
    if state.intent in {"product_search", "general_question"}:
        return "retrieval"
    return "guardrails"


def route_after_guardrails(state: AgentState) -> str:
    """Decide the next node after the guardrail evaluation.

    Args:
        state: Current agent state after guardrail checks.

    Returns:
        ``"fallback"`` when the message was blocked or produced no verified
        results, otherwise ``"response_generator"``.
    """
    if state.guardrail_blocked:
        return "fallback"
    if state.intent == "product_search" and not state.retrieved_products:
        return "fallback"
    if state.intent == "general_question" and not state.retrieved_knowledge:
        return "fallback"
    return "response_generator"


def build_graph():
    """Build and compile the LangGraph state machine.

    Registers the five nodes (``intent_router``, ``retrieval``, ``guardrails``,
    ``response_generator``, ``fallback``), connects them with the routing
    functions above, and returns a compiled graph ready to ``invoke``.

    Returns:
        A compiled LangGraph ``StateGraph`` instance.
    """
    graph = StateGraph(AgentState)
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("response_generator", response_generator_node)
    graph.add_node("fallback", fallback_node)

    graph.add_edge(START, "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "retrieval": "retrieval",
            "guardrails": "guardrails",
        },
    )
    graph.add_edge("retrieval", "guardrails")
    graph.add_conditional_edges(
        "guardrails",
        route_after_guardrails,
        {
            "response_generator": "response_generator",
            "fallback": "fallback",
        },
    )
    graph.add_edge("response_generator", END)
    graph.add_edge("fallback", END)
    return graph.compile()
