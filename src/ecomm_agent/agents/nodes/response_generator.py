from ecomm_agent.agents.state import AgentState
from ecomm_agent.services.inventory import filter_available_variants
from ecomm_agent.services.urls import build_product_page_url


def response_generator_node(state: AgentState) -> AgentState:
    if state.guardrail_blocked:
        if state.guardrail_reason == "prompt_injection":
            message = (
                "I can only help with verified Nova Style catalog information. "
                "Ask about products, prices, colors, sizes, or stock."
            )
        else:
            message = (
                "I can only answer with verified catalog data from Nova Style. "
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
                    "I can help you find Nova Style products and confirm verified prices, "
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
