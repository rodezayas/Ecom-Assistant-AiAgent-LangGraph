from ecomm_agent.core.config import settings


def build_product_page_url(product_id: str) -> str | None:
    if not settings.frontend_base_url:
        return None
    return f"{settings.frontend_base_url.rstrip('/')}/products/{product_id}"
