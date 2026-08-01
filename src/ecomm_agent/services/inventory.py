"""Inventory logic.

Read-only operations over product variants. All stock and availability data
returned here comes directly from the catalog source of truth -- never from
the LLM.
"""

from ecomm_agent.schemas.catalog import Product


def filter_available_variants(
    product: Product,
    *,
    size: str | None = None,
    color: str | None = None,
) -> list[dict[str, str | int]]:
    """Return in-stock variants matching optional size/color filters.

    A variant is included only when it has positive stock and, when filters
    are provided, matches the requested size and color exactly.

    Args:
        product: The product whose variants to filter.
        size: Optional size filter (compared case-insensitively).
        color: Optional color filter (compared case-insensitively).

    Returns:
        A list of dicts with ``sku``, ``size``, ``color``, and ``stock`` keys
        for each matching in-stock variant.
    """
    return [
        {
            "sku": variant.sku,
            "size": variant.size,
            "color": variant.color,
            "stock": variant.stock,
        }
        for variant in product.variants
        if variant.stock > 0
        and (size is None or variant.size.upper() == size)
        and (color is None or variant.color.lower() == color)
    ]
