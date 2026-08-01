"""Deterministic URL construction.

Product page URLs are derived from the product identifier and the configured
frontend base URL. URLs are never produced by the LLM -- they are resolved
deterministically from configuration.
"""

from ecomm_agent.core.config import settings


def build_product_page_url(product_id: str) -> str | None:
    """Build the public product page URL for a product.

    Args:
        product_id: The stable product identifier (e.g. ``TSH-001``).

    Returns:
        The URL ``{frontend_base_url}/products/{product_id}``, or ``None``
        when ``FRONTEND_BASE_URL`` is not configured.
    """
    if not settings.frontend_base_url:
        return None
    return f"{settings.frontend_base_url.rstrip('/')}/products/{product_id}"
