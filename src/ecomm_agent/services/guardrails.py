"""Deterministic business guardrails.

Blocks unsafe or out-of-scope messages before any LLM generation:

- **prompt injection**: distinctive phrases attempting to override the
  assistant's instructions or reveal its system prompt;
- **out of scope**: messages whose meaningful vocabulary is not covered by
  the catalog, the knowledge base, and the fixed commerce terms.

The allowed vocabulary is derived from the source of truth (catalog +
knowledge documents), which keeps scope detection tied to actual inventory
rather than to a model's judgment.
"""

import re
from dataclasses import dataclass

from ecomm_agent.core.domain import (
    BRAND_NAME,
    COMMERCE_TERMS,
    PROMPT_INJECTION_PATTERNS,
    SAFE_STOPWORDS,
)
from ecomm_agent.schemas.catalog import Product


# Matches alphanumeric tokens, optionally with hyphens (e.g. "t-shirt").
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9\-]+")


@dataclass(frozen=True)
class GuardrailResult:
    """Outcome of a guardrail evaluation."""

    allowed: bool
    """True when the message may proceed."""

    reason: str | None = None
    """Guardrail trigger: ``prompt_injection`` or ``out_of_scope``."""

    matched_terms: tuple[str, ...] = ()
    """The specific terms or phrases that triggered the block."""


def tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens.

    Args:
        text: Raw text to tokenize.

    Returns:
        A list of lowercase tokens.
    """
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def build_allowed_vocabulary(
    products: list[Product],
    *,
    extra_texts: list[str] | None = None,
) -> set[str]:
    """Build the vocabulary of words the store legitimately talks about.

    The vocabulary is the union of the brand name, the fixed commerce terms,
    every token appearing in the catalog (names, categories, descriptions,
    tags, colors, sizes), and any extra texts such as knowledge documents.

    Args:
        products: Catalog products whose text feeds the vocabulary.
        extra_texts: Additional documents (e.g. policy text) to include.

    Returns:
        The set of allowed lowercase tokens.
    """
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

    for text in extra_texts or []:
        vocabulary.update(tokenize(text))

    return vocabulary


def detect_prompt_injection(text: str) -> tuple[str, ...]:
    """Detect prompt-injection phrases in a message.

    Args:
        text: The user message.

    Returns:
        A tuple of the injection phrases present (empty when none match).
    """
    lowered = text.lower()
    return tuple(
        pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern in lowered
    )


def detect_out_of_scope_terms(text: str, allowed_vocabulary: set[str]) -> tuple[str, ...]:
    """Detect message tokens that fall outside the store's domain.

    Meaningful tokens (not stopwords, not digits, longer than two characters)
    are compared against the allowed vocabulary. A message is considered out
    of scope when it has at least two unknown terms and no strong budget
    signal or enough in-domain product signals.

    Args:
        text: The user message.
        allowed_vocabulary: Vocabulary built by
            :func:`build_allowed_vocabulary`.

    Returns:
        A tuple of unknown terms when the message is out of scope, otherwise
        an empty tuple.
    """
    tokens = tokenize(text)
    # Only meaningful tokens count toward scope: drop stopwords, digits, and
    # very short tokens that carry no domain signal.
    meaningful_tokens = [
        token
        for token in tokens
        if token not in SAFE_STOPWORDS and not token.isdigit() and len(token) > 2
    ]
    unknown_terms = [
        token for token in meaningful_tokens if token not in allowed_vocabulary
    ]

    # In-domain tokens are a signal the message is still on-topic.
    product_signals = [token for token in meaningful_tokens if token in allowed_vocabulary]
    has_budget_signal = any(token.isdigit() for token in tokens)

    # A budget amount ("under 1500") is a strong store intent, so never flag
    # such messages as out of scope even if some words are unfamiliar.
    if has_budget_signal:
        return ()

    # Allow the message when it has at least as many in-domain signals as
    # unknown terms; a single unknown word is tolerated.
    if product_signals and len(product_signals) >= len(unknown_terms):
        return ()

    # Two or more unknown terms means the request left the store's domain.
    if len(unknown_terms) >= 2:
        return tuple(sorted(set(unknown_terms)))

    return ()


def evaluate_message_guardrails(
    text: str,
    allowed_vocabulary: set[str],
) -> GuardrailResult:
    """Evaluate a message against the full guardrail set.

    Prompt injection is checked first; if none is found, the message is
    checked for out-of-scope terms.

    Args:
        text: The user message.
        allowed_vocabulary: Vocabulary built by
            :func:`build_allowed_vocabulary`.

    Returns:
        A :class:`GuardrailResult` describing whether the message is allowed
        and, if not, why.
    """
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
