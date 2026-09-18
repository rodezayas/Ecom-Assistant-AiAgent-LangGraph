"""Response generation node.

Builds a deterministic reply from verified state. Product replies list the
retrieved products with their verified prices, available variants, and
product page URLs; general questions list the retrieved knowledge snippets.
This node never invents data -- it renders what retrieval produced.
"""

from ecomm_agent.agents.state import AgentState
from ecomm_agent.observability.tracing import get_tracer, is_content_recording_enabled
from ecomm_agent.services.inventory import filter_available_variants
from ecomm_agent.services.urls import build_product_page_url

tracer = get_tracer(__name__)


def response_generator_node(state: AgentState) -> AgentState:
    """Compose the deterministic reply text for the current state.

    Order of precedence:

    - Guardrail-blocked messages get a canned safe reply.
    - General questions render verified knowledge snippets, or a generic
      capability message when nothing was retrieved.
    - Product searches render verified matches with prices, in-stock
      variants, and (when configured) product page URLs.

    Args:
        state: Agent state with retrieval and guardrail results populated.

    Returns:
        A copy of the state with ``response_text`` set.
    """
    with tracer.start_as_current_span("response_generator") as span:
        result = _build_response(state)
        try:
            span.set_attribute("thread_id", state.thread_id)
            span.set_attribute("intent", state.intent or "")
            span.set_attribute("response.length", len(result.response_text or ""))
            if is_content_recording_enabled() and result.response_text:
                span.set_attribute("input.value", state.user_message[:2000])
                span.set_attribute("output.value", result.response_text[:4000])
        except Exception:
            pass
        return result


def _build_response(state: AgentState) -> AgentState:
    if state.guardrail_blocked:
        if state.guardrail_reason == "prompt_injection":
            message = (
                "I can only help with verified Alta Norma Fashion catalog information. "
                "Ask about products, prices, colors, sizes, or stock."
            )
        else:
            message = (
                "I can only answer with verified catalog data from Alta Norma Fashion. "
                "Ask about products, prices, sizes, colors, or availability."
            )
        return state.model_copy(update={"response_text": message})

    if state.intent != "product_search":
        if state.retrieved_knowledge:
            lines = ["Here is the closest verified guidance I found:"]
            for snippet in state.retrieved_knowledge[:3]:
                label = snippet.section.replace("_", " ").title() if snippet.section else snippet.source_type
                lines.append(f"- {label}: {snippet.content}")
            return state.model_copy(update={"response_text": "\n".join(lines)})

        return state.model_copy(
            update={
                "response_text": (
                    "I can help you find Alta Norma Fashion products and confirm verified prices, "
                    "sizes, colors, stock, shipping, returns, and size guidance."
                )
            }
        )

    lines = ["Here are the closest verified matches from the catalog:"]
    for product in state.retrieved_products:
        variants = filter_available_variants(
            product,
            size=state.requested_size,
            color=state.requested_color,
        )
        variant_summary = ", ".join(
            f"{item['color']} {item['size']} (stock {item['stock']})"
            for item in variants[:3]
        )
        if not variant_summary:
            variant_summary = "available variants require a broader size/color query"
        product_line = (
            f"- {product.name} ({product.category}) - ${product.price:.2f}. {variant_summary}."
        )
        product_url = build_product_page_url(product.id)
        if product_url:
            product_line = f"{product_line} View product: {product_url}"
        lines.append(product_line)

    return state.model_copy(update={"response_text": "\n".join(lines)})
