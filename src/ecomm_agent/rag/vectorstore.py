from ecomm_agent.schemas.catalog import Product


def build_product_document(product: Product) -> str:
    return " | ".join(
        [
            product.name,
            product.description,
            product.category,
            ", ".join(product.tags),
        ]
    )
