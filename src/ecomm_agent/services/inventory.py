from ecomm_agent.schemas.catalog import Product


def get_available_variants(product: Product) -> list[dict[str, str | int]]:
    return [
        {
            "sku": variant.sku,
            "size": variant.size,
            "color": variant.color,
            "stock": variant.stock,
        }
        for variant in product.variants
    ]


def filter_available_variants(
    product: Product,
    *,
    size: str | None = None,
    color: str | None = None,
) -> list[dict[str, str | int]]:
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
