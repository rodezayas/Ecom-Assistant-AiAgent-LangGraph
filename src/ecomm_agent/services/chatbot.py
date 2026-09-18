"""High-level chatbot entry points.

Ties the compiled LangGraph to the LLM generation path: runs a user message
through the graph and produces the final reply text, preferring the LLM
reply and falling back to the deterministic ``response_text`` produced by the
graph.
"""

from ecomm_agent.agents.graph import build_graph
from ecomm_agent.agents.state import AgentState
from ecomm_agent.observability.tracing import get_tracer, is_content_recording_enabled
from ecomm_agent.services.llm import generate_response_text

tracer = get_tracer(__name__)

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
    with tracer.start_as_current_span("agent.graph") as span:
        try:
            span.set_attribute("thread_id", thread_id)
            if is_content_recording_enabled():
                span.set_attribute("input.value", text[:2000])
        except Exception:
            pass
        state = AgentState(thread_id=thread_id, user_message=text)
        result = GRAPH.invoke(state)
        final = result if isinstance(result, AgentState) else AgentState.model_validate(result)
        try:
            span.set_attribute("intent", final.intent or "")
            span.set_attribute("guardrail.blocked", final.guardrail_blocked)
            span.set_attribute("retrieval.product_count", len(final.retrieved_products))
            span.set_attribute("retrieval.knowledge_count", len(final.retrieved_knowledge))
            if is_content_recording_enabled() and final.response_text:
                span.set_attribute("output.value", final.response_text[:4000])
        except Exception:
            pass
        return final


async def build_reply_text(state: AgentState) -> str:
    """Produce the final reply text for a completed conversation turn.

    Tries the LLM generation providers first; when none returns a reply, the
    deterministic ``state.response_text`` produced by the graph is used.

    Args:
        state: Agent state after graph execution.

    Returns:
        The final reply text to send to the user.
    """
    with tracer.start_as_current_span("agent.build_reply") as span:
        try:
            span.set_attribute("thread_id", state.thread_id)
            span.set_attribute("intent", state.intent or "")
        except Exception:
            pass
        llm_response = await generate_response_text(state)
        if llm_response:
            try:
                span.set_attribute("reply.source", "llm")
                if is_content_recording_enabled():
                    span.set_attribute("output.value", llm_response[:4000])
            except Exception:
                pass
            return llm_response

        fallback = state.response_text or (
            "I can help with verified Alta Norma Fashion products, prices, colors, sizes, and stock."
        )
        try:
            span.set_attribute("reply.source", "deterministic")
            if is_content_recording_enabled():
                span.set_attribute("output.value", fallback[:4000])
        except Exception:
            pass
        return fallback
