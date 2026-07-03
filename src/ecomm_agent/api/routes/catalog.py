from fastapi import APIRouter, HTTPException, status

from ecomm_agent.core.config import settings
from ecomm_agent.schemas.catalog import Product
from ecomm_agent.services.catalog import load_catalog

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _load_catalog() -> list[Product]:
    return load_catalog(settings.catalog_path)


@router.get("", response_model=list[Product])
def list_catalog() -> list[Product]:
    return _load_catalog()


@router.get("/{product_id}", response_model=Product)
def get_catalog_product(product_id: str) -> Product:
    product = next(
        (item for item in _load_catalog() if item.id == product_id),
        None,
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' was not found in the catalog.",
        )
    return product
