from langgraph.graph import END, START, StateGraph

from ecomm_agent.agents.nodes.fallback import fallback_node
from ecomm_agent.agents.nodes.guardrails import guardrails_node
from ecomm_agent.agents.nodes.intent_router import intent_router_node
from ecomm_agent.agents.nodes.response_generator import response_generator_node
from ecomm_agent.agents.nodes.retrieval import retrieval_node
from ecomm_agent.agents.state import AgentState


def route_after_intent(state: AgentState) -> str:
    if state.intent in {"product_search", "general_question"}:
        return "retrieval"
    return "guardrails"


def route_after_retrieval(state: AgentState) -> str:
    return "guardrails"


def route_after_guardrails(state: AgentState) -> str:
    if state.guardrail_blocked:
        return "fallback"
    if state.intent == "product_search" and not state.retrieved_products:
        return "fallback"
    if state.intent == "general_question" and not state.retrieved_knowledge:
        return "fallback"
    return "response_generator"


def build_graph():
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
    graph.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "guardrails": "guardrails",
        },
    )
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
