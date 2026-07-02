import json
import re
from dataclasses import dataclass
from pathlib import Path

from ecomm_agent.core.domain import SAFE_STOPWORDS
from ecomm_agent.services.guardrails import tokenize
from ecomm_agent.schemas.catalog import Product


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

CATEGORY_SYNONYMS = {
    "t-shirts": {"t-shirt", "tshirts", "tshirt", "tee", "tees", "shirt", "shirts"},
    "pants": {"pant", "pants", "trouser", "trousers", "jogger", "joggers", "jeans"},
    "jackets": {"jacket", "jackets", "outerwear", "vest"},
    "shoes": {"shoe", "shoes", "sneaker", "sneakers", "runner", "runners"},
    "accessories": {"accessory", "accessories", "cap", "caps", "bag", "bags", "belt"},
}

PRICE_PATTERN = re.compile(
    r"(?:under|below|less than|up to)\s*\$?\s*(\d+(?:\.\d+)?)|\$?\s*(\d+(?:\.\d+)?)\s*(?:or less|max)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SearchFilters:
    category: str | None = None
    color: str | None = None
    size: str | None = None
    price_ceiling: float | None = None
    query_terms: tuple[str, ...] = ()


def load_catalog(path: str) -> list[Product]:
    catalog_path = Path(path)
    if not catalog_path.exists():
        return []
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return [Product.model_validate(item) for item in data]


def extract_search_filters(text: str, catalog: list[Product]) -> SearchFilters:
    tokens = tokenize(text)
    catalog_colors = {
        variant.color.lower()
        for product in catalog
        for variant in product.variants
    }

    category = None
    for candidate, synonyms in CATEGORY_SYNONYMS.items():
        if candidate in tokens or any(term in tokens for term in synonyms):
            category = candidate
            break

    color = next((token for token in tokens if token in catalog_colors), None)
    size = next((SIZE_NORMALIZATION[token] for token in tokens if token in SIZE_NORMALIZATION), None)

    price_ceiling = None
    price_match = PRICE_PATTERN.search(text)
    if price_match:
        price_value = price_match.group(1) or price_match.group(2)
        if price_value:
            price_ceiling = float(price_value)

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
    filters = extract_search_filters(text, catalog)
    scored_products: list[tuple[int, Product]] = []

    for product in catalog:
        if filters.category and product.category != filters.category:
            continue
        if filters.price_ceiling is not None and product.price > filters.price_ceiling:
            continue

        matching_variants = [
            variant
            for variant in product.variants
            if (filters.color is None or variant.color.lower() == filters.color)
            and (filters.size is None or variant.size.upper() == filters.size)
            and variant.stock > 0
        ]
        if (filters.color or filters.size) and not matching_variants:
            continue

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

        if score > 0 or not filters.query_terms:
            scored_products.append((score, product))

    scored_products.sort(key=lambda item: (-item[0], item[1].price, item[1].name))
    return [product for _, product in scored_products[:limit]], filters
