"""Retrieval node.

Executes retrieval for the classified intent: product search queries the
catalog, while general questions query the knowledge base. The extracted
filters (category, color, size, price ceiling) are written back to state so
downstream nodes and the LLM only ever see verified data.
"""

from ecomm_agent.agents.state import AgentState
from ecomm_agent.observability.tracing import get_tracer, is_content_recording_enabled
from ecomm_agent.services.retrieval import retrieve_knowledge, retrieve_products

tracer = get_tracer(__name__)


def retrieval_node(state: AgentState) -> AgentState:
    """Run catalog or knowledge retrieval depending on the intent.

    Args:
        state: Agent state with ``intent`` populated by the intent router.

    Returns:
        A copy of the state with the retrieved products/knowledge and the
        extracted request filters. ``retrieval_reason`` is set to
        ``no_results`` when nothing is found.
    """
    with tracer.start_as_current_span("retrieval") as span:
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

            result = state.model_copy(
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
            try:
                span.set_attribute("thread_id", state.thread_id)
                span.set_attribute("intent", state.intent or "")
                span.set_attribute("retrieval.type", "product")
                span.set_attribute("retrieval.product_count", len(products))
                span.set_attribute("retrieval.reason", retrieval_reason or "")
                if category:
                    span.set_attribute("retrieval.category", category)
                if color:
                    span.set_attribute("retrieval.color", color)
                if size:
                    span.set_attribute("retrieval.size", size)
                if price_ceiling is not None:
                    span.set_attribute("retrieval.price_ceiling", float(price_ceiling))
                if is_content_recording_enabled():
                    span.set_attribute("input.value", state.user_message[:2000])
                    span.set_attribute(
                        "output.value",
                        ", ".join(p.id for p in products[:5]) or retrieval_reason or "no_results",
                    )
                    for idx, prod in enumerate(products[:3]):
                        span.set_attribute(f"retrieval.documents.{idx}.document.id", prod.id)
                        span.set_attribute(f"retrieval.documents.{idx}.document.content", prod.name[:500])
            except Exception:
                pass
            return result

        knowledge = retrieve_knowledge(state.user_message)
        if not knowledge:
            retrieval_reason = "no_results"

        result = state.model_copy(
            update={
                "retrieved_products": [],
                "retrieved_knowledge": knowledge,
                "retrieval_reason": retrieval_reason,
            }
        )
        try:
            span.set_attribute("thread_id", state.thread_id)
            span.set_attribute("intent", state.intent or "")
            span.set_attribute("retrieval.type", "knowledge")
            span.set_attribute("retrieval.knowledge_count", len(knowledge))
            span.set_attribute("retrieval.reason", retrieval_reason or "")
            if is_content_recording_enabled():
                span.set_attribute("input.value", state.user_message[:2000])
                span.set_attribute(
                    "output.value",
                    "; ".join(k.content[:300] for k in knowledge[:2]) or retrieval_reason or "no_results",
                )
        except Exception:
            pass
        return result
