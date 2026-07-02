from langgraph.graph import END, START, StateGraph

from ecomm_agent.agents.nodes.fallback import fallback_node
from ecomm_agent.agents.nodes.guardrails import guardrails_node
from ecomm_agent.agents.nodes.intent_router import intent_router_node
from ecomm_agent.agents.nodes.response_generator import response_generator_node
from ecomm_agent.agents.nodes.retrieval import retrieval_node
from ecomm_agent.agents.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("response_generator", response_generator_node)
    graph.add_node("fallback", fallback_node)

    graph.add_edge(START, "intent_router")
    graph.add_edge("intent_router", "retrieval")
    graph.add_edge("retrieval", "guardrails")
    graph.add_edge("guardrails", "response_generator")
    graph.add_edge("response_generator", END)
    graph.add_edge("fallback", END)
    return graph.compile()
