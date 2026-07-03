from __future__ import annotations

from textwrap import dedent

import httpx

from ecomm_agent.agents.state import AgentState
from ecomm_agent.core.config import settings
from ecomm_agent.services.inventory import filter_available_variants
from ecomm_agent.services.urls import build_product_page_url


def _build_product_context(state: AgentState) -> str:
    if not state.retrieved_products:
        return "No verified product matches were found."

    lines: list[str] = []
    for product in state.retrieved_products:
        variants = filter_available_variants(
            product,
            size=state.requested_size,
            color=state.requested_color,
        )
        variant_text = ", ".join(
            f"{variant['color']} {variant['size']} stock={variant['stock']}"
            for variant in variants[:5]
        )
        if not variant_text:
            variant_text = "No verified variants matched the requested size/color filters."
        product_url = build_product_page_url(product.id) or "No verified product page URL configured."
        lines.append(
            f"- {product.name} | category={product.category} | price=${product.price:.2f} | variants={variant_text} | product_url={product_url}"
        )

    return "\n".join(lines)


def _build_knowledge_context(state: AgentState) -> str:
    if not state.retrieved_knowledge:
        return "No verified policy, FAQ, or size-guide snippets were found."

    lines = []
    for snippet in state.retrieved_knowledge:
        label = snippet.section or snippet.source_type
        lines.append(
            f"- source_type={snippet.source_type} | section={label} | content={snippet.content}"
        )
    return "\n".join(lines)


def _build_user_prompt(state: AgentState) -> str:
    return dedent(
        f"""
        Customer message:
        {state.user_message}

        Classified intent:
        {state.intent or "unknown"}

        Guardrail blocked:
        {state.guardrail_blocked}
        Guardrail reason:
        {state.guardrail_reason or "none"}

        Requested filters:
        category={state.requested_category or "none"}
        color={state.requested_color or "none"}
        size={state.requested_size or "none"}
        max_price={state.price_ceiling if state.price_ceiling is not None else "none"}

        Verified catalog context:
        {_build_product_context(state)}

        Verified knowledge-base context:
        {_build_knowledge_context(state)}

        Deterministic fallback response:
        {state.response_text or ""}
        """
    ).strip()


def _build_system_prompt() -> str:
    return dedent(
        """
        You are Nova Style's Telegram sales assistant.
        Answer in plain text suitable for Telegram.
        Use only the verified catalog and knowledge-base context provided to you.
        Never invent products, prices, sizes, colors, stock, shipping promises, or discounts.
        If a verified product_url is provided in catalog context, you may include it in the reply.
        If no verified product is available, say so directly and suggest a broader search.
        Keep the answer concise and helpful.
        """
    ).strip()


async def _generate_response_text_anthropic(state: AgentState) -> str | None:
    if not settings.anthropic_api_key:
        return None

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": settings.anthropic_max_tokens,
        "system": _build_system_prompt(),
        "messages": [
            {
                "role": "user",
                "content": _build_user_prompt(state),
            }
        ],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": settings.anthropic_api_version,
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.anthropic_api_base_url.rstrip('/')}/v1/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    body = response.json()
    content_blocks = body.get("content", [])
    text_parts = [
        block.get("text", "")
        for block in content_blocks
        if block.get("type") == "text" and block.get("text")
    ]
    text = "\n".join(text_parts).strip()
    return text or None


async def _generate_response_text_groq(state: AgentState) -> str | None:
    if not settings.groq_api_key:
        return None

    payload = {
        "model": settings.groq_model,
        "max_completion_tokens": settings.groq_max_completion_tokens,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": _build_system_prompt(),
            },
            {
                "role": "user",
                "content": _build_user_prompt(state),
            },
        ],
    }
    headers = {
        "authorization": f"Bearer {settings.groq_api_key}",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{settings.groq_api_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    body = response.json()
    choices = body.get("choices", [])
    if not choices:
        return None

    message = choices[0].get("message", {})
    text = message.get("content", "")
    return text.strip() or None


async def generate_response_text(state: AgentState) -> str | None:
    try:
        anthropic_response = await _generate_response_text_anthropic(state)
    except Exception:
        anthropic_response = None

    if anthropic_response:
        return anthropic_response

    try:
        groq_response = await _generate_response_text_groq(state)
    except Exception:
        groq_response = None

    if groq_response:
        return groq_response

    return None
