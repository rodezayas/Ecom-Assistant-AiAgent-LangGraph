import re
from dataclasses import dataclass

from ecomm_agent.core.domain import (
    BRAND_NAME,
    COMMERCE_TERMS,
    PROMPT_INJECTION_PATTERNS,
    SAFE_STOPWORDS,
)
from ecomm_agent.schemas.catalog import Product


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\-]+")


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    matched_terms: tuple[str, ...] = ()


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def build_allowed_vocabulary(products: list[Product]) -> set[str]:
    vocabulary = set(tokenize(BRAND_NAME))
    vocabulary.update(COMMERCE_TERMS)

    for product in products:
        vocabulary.update(tokenize(product.name))
        vocabulary.update(tokenize(product.category))
        vocabulary.update(tokenize(product.description))
        vocabulary.update(tokenize(" ".join(product.tags)))
        for variant in product.variants:
            vocabulary.update(tokenize(variant.color))
            vocabulary.update(tokenize(variant.size))

    return vocabulary


def detect_prompt_injection(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(
        pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern in lowered
    )


def detect_out_of_scope_terms(text: str, allowed_vocabulary: set[str]) -> tuple[str, ...]:
    tokens = tokenize(text)
    meaningful_tokens = [
        token
        for token in tokens
        if token not in SAFE_STOPWORDS and not token.isdigit() and len(token) > 2
    ]
    unknown_terms = [
        token for token in meaningful_tokens if token not in allowed_vocabulary
    ]

    product_signals = [token for token in meaningful_tokens if token in allowed_vocabulary]
    has_budget_signal = any(token.isdigit() for token in tokens)

    if product_signals or has_budget_signal:
        return ()

    if len(unknown_terms) >= 2:
        return tuple(sorted(set(unknown_terms)))

    return ()


def evaluate_message_guardrails(
    text: str,
    allowed_vocabulary: set[str],
) -> GuardrailResult:
    injection_matches = detect_prompt_injection(text)
    if injection_matches:
        return GuardrailResult(
            allowed=False,
            reason="prompt_injection",
            matched_terms=injection_matches,
        )

    out_of_scope_terms = detect_out_of_scope_terms(text, allowed_vocabulary)
    if out_of_scope_terms:
        return GuardrailResult(
            allowed=False,
            reason="out_of_scope",
            matched_terms=out_of_scope_terms,
        )

    return GuardrailResult(allowed=True)
