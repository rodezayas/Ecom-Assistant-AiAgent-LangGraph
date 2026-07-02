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
