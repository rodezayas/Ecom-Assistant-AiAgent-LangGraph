"""Catalog API routes.

Read-only endpoints exposing the same source-of-truth catalog used by the
agent, so the website layer can render product pages without duplicating data.
Only ``GET`` is exposed.
"""

import re

from fastapi import APIRouter, HTTPException, Request, status

from ecomm_agent.api.security import check_rate_limit
from ecomm_agent.core.config import settings
from ecomm_agent.schemas.catalog import Product
from ecomm_agent.services.catalog import load_catalog

_PRODUCT_ID_RE = re.compile(r"^[A-Za-z0-9\-]{1,30}$")

# Read-only catalog endpoints consumed by the website layer.
router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _load_catalog() -> list[Product]:
    """Load the catalog from the configured path.

    Returns:
        The full validated product catalog.
    """
    return load_catalog(settings.catalog_path)


@router.get("", response_model=list[Product])
def list_catalog(request: Request) -> list[Product]:
    """Return the full product catalog.

    Returns:
        The complete list of catalog products.
    """
    check_rate_limit(request, settings.rate_limit_catalog_per_minute)
    return _load_catalog()


@router.get("/{product_id}", response_model=Product)
def get_catalog_product(product_id: str, request: Request) -> Product:
    """Return a single catalog product by id.

    Args:
        product_id: The product identifier (e.g. ``TSH-001``).

    Returns:
        The matching product.

    Raises:
        HTTPException: With status 404 when the product does not exist.
    """
    check_rate_limit(request, settings.rate_limit_catalog_per_minute)
    if not _PRODUCT_ID_RE.match(product_id) or len(product_id) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product_id format.",
        )
    product = next(
        (item for item in _load_catalog() if item.id == product_id),
        None,
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    return product
