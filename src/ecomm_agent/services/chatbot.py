"""High-level chatbot entry points.

Ties the compiled LangGraph to the LLM generation path: runs a user message
through the graph and produces the final reply text, preferring the LLM
reply and falling back to the deterministic ``response_text`` produced by the
graph.
"""

from ecomm_agent.agents.graph import build_graph
from ecomm_agent.agents.state import AgentState
from ecomm_agent.services.llm import generate_response_text


GRAPH = build_graph()
"""Compiled LangGraph instance, built once at import time."""


def process_user_message(thread_id: str, text: str) -> AgentState:
    """Run a user message through the agent graph.

    Args:
        thread_id: Per-conversation identifier (the Telegram ``chat.id``).
        text: The user message text.

    Returns:
        The final agent state after the graph completes.
    """
    state = AgentState(thread_id=thread_id, user_message=text)
    result = GRAPH.invoke(state)
    if isinstance(result, AgentState):
        return result
    return AgentState.model_validate(result)


async def build_reply_text(state: AgentState) -> str:
    """Produce the final reply text for a completed conversation turn.

    Tries the LLM generation providers first; when none returns a reply, the
    deterministic ``state.response_text`` produced by the graph is used.

    Args:
        state: Agent state after graph execution.

    Returns:
        The final reply text to send to the user.
    """
    llm_response = await generate_response_text(state)
    if llm_response:
        return llm_response

    return state.response_text or (
        "I can help with verified Alta Norma Fashion products, prices, colors, sizes, and stock."
    )
