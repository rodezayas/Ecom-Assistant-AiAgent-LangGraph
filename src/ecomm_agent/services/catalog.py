"""Deterministic catalog access and lexical search.

Loads the source-of-truth product catalog from JSON and provides:
- normalization of user-provided sizes and categories,
- extraction of search filters (category, color, size, price ceiling),
- a lexical scoring search over product name/description/category/tags.

This module is the deterministic counterpart of semantic retrieval: it is
used both as the primary search path and as the fallback when the vector
store is unavailable.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ecomm_agent.core.domain import SAFE_STOPWORDS
from ecomm_agent.services.guardrails import tokenize
from ecomm_agent.schemas.catalog import Product


# Maps free-text size words to the canonical size labels used by the catalog.
SIZE_NORMALIZATION = {
    "small": "S",
    "s": "S",
    "medium": "M",
    "m": "M",
    "large": "L",
    "l": "L",
    "xl": "XL",
    "extra-large": "XL",
}

# Maps each canonical category to the set of synonyms that should match it.
CATEGORY_SYNONYMS = {
    "t-shirts": {"t-shirt", "tshirts", "tshirt", "tee", "tees", "shirt", "shirts"},
    "pants": {"pant", "pants", "trouser", "trousers", "jogger", "joggers", "jeans"},
    "jackets": {"jacket", "jackets", "outerwear", "vest"},
    "shoes": {"shoe", "shoes", "sneaker", "sneakers", "runner", "runners"},
    "accessories": {"accessory", "accessories", "cap", "caps", "bag", "bags", "belt"},
}

# Matches price ceilings phrased as "under/below/less than/up to $X" or
# "$X or less/max".
PRICE_PATTERN = re.compile(
    r"(?:under|below|less than|up to)\s*\$?\s*(\d+(?:\.\d+)?)|\$?\s*(\d+(?:\.\d+)?)\s*(?:or less|max)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SearchFilters:
    """Structured filters extracted from a free-text search query."""

    category: str | None = None
    """Canonical category matched via :data:`CATEGORY_SYNONYMS`, if any."""

    color: str | None = None
    """Color matched against the catalog's variant colors, if any."""

    size: str | None = None
    """Normalized size (S/M/L/XL) matched via :data:`SIZE_NORMALIZATION`."""

    price_ceiling: float | None = None
    """Maximum price extracted from the query, if any."""

    query_terms: tuple[str, ...] = ()
    """Remaining meaningful tokens used for lexical scoring."""


def load_catalog(path: str) -> list[Product]:
    """Load and validate the product catalog from a JSON file.

    Args:
        path: Filesystem path to the catalog JSON.

    Returns:
        A list of validated :class:`Product` objects. Returns an empty list
        when the file does not exist.
    """
    catalog_path = Path(path)
    if not catalog_path.exists():
        return []
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return [Product.model_validate(item) for item in data]


def extract_search_filters(text: str, catalog: list[Product]) -> SearchFilters:
    """Extract structured filters from a free-text query.

    Recognizes category synonyms, colors that exist in the catalog, normalized
    sizes, and price ceilings. Remaining meaningful tokens become
    ``query_terms`` for lexical scoring.

    Args:
        text: The user's free-text query.
        catalog: The product catalog used to build the set of known colors.

    Returns:
        A :class:`SearchFilters` instance with the extracted values.
    """
    tokens = tokenize(text)
    # Only colors that actually exist in the catalog count as color filters.
    catalog_colors = {
        variant.color.lower()
        for product in catalog
        for variant in product.variants
    }

    # Match the query against each category and its synonyms.
    category = None
    for candidate, synonyms in CATEGORY_SYNONYMS.items():
        if candidate in tokens or any(term in tokens for term in synonyms):
            category = candidate
            break

    # Pick the first known color and the first known size mentioned.
    color = next((token for token in tokens if token in catalog_colors), None)
    size = next((SIZE_NORMALIZATION[token] for token in tokens if token in SIZE_NORMALIZATION), None)

    # Extract a "under/up to $X" price ceiling when the query phrases it that way.
    price_ceiling = None
    price_match = PRICE_PATTERN.search(text)
    if price_match:
        price_value = price_match.group(1) or price_match.group(2)
        if price_value:
            price_ceiling = float(price_value)

    # Remaining meaningful tokens for lexical scoring: drop stopwords, digits,
    # colors, sizes, and very short tokens.
    query_terms = tuple(
        token
        for token in tokens
        if token not in SAFE_STOPWORDS
        and not token.isdigit()
        and token not in catalog_colors
        and token not in SIZE_NORMALIZATION
        and len(token) > 2
    )

    return SearchFilters(
        category=category,
        color=color,
        size=size,
        price_ceiling=price_ceiling,
        query_terms=query_terms,
    )


def search_catalog(
    text: str,
    catalog: list[Product],
    *,
    limit: int = 3,
) -> tuple[list[Product], SearchFilters]:
    """Lexically score and rank products against a query.

    Products are filtered by category, price ceiling, and (when requested)
    size/color availability, then scored by how many query terms appear in
    the product's name, description, category, and tags. Category, color,
    size, and price matches add bonus weight.

    Args:
        text: The user's free-text query.
        catalog: Product candidates to search.
        limit: Maximum number of products to return.

    Returns:
        A tuple of the top-ranked products and the extracted
        :class:`SearchFilters`.
    """
    filters = extract_search_filters(text, catalog)
    scored_products: list[tuple[int, Product]] = []

    for product in catalog:
        # Hard filters first: category and price ceiling reject products
        # deterministically before any scoring happens.
        if filters.category and product.category != filters.category:
            continue
        if filters.price_ceiling is not None and product.price > filters.price_ceiling:
            continue

        # When a size/color is requested, only keep products with a matching
        # in-stock variant; otherwise every product survives this step.
        matching_variants = [
            variant
            for variant in product.variants
            if (filters.color is None or variant.color.lower() == filters.color)
            and (filters.size is None or variant.size.upper() == filters.size)
            and variant.stock > 0
        ]
        if (filters.color or filters.size) and not matching_variants:
            continue

        # Lexical overlap score, with bonus weight for each matched filter so
        # perfect fits rank above products that merely share a term.
        document_tokens = set(
            tokenize(
                " ".join(
                    [
                        product.name,
                        product.description,
                        product.category,
                        " ".join(product.tags),
                    ]
                )
            )
        )
        score = sum(1 for term in filters.query_terms if term in document_tokens)
        if filters.category and product.category == filters.category:
            score += 3
        if filters.color and any(variant.color.lower() == filters.color for variant in matching_variants):
            score += 2
        if filters.size and any(variant.size.upper() == filters.size for variant in matching_variants):
            score += 2
        if filters.price_ceiling is not None:
            score += 1

        # Keep anything with a positive score, or all products when the query
        # carried no meaningful terms (e.g. just "shoes").
        if score > 0 or not filters.query_terms:
            scored_products.append((score, product))

    # Highest score first; ties broken by lowest price and then name.
    scored_products.sort(key=lambda item: (-item[0], item[1].price, item[1].name))
    return [product for _, product in scored_products[:limit]], filters
