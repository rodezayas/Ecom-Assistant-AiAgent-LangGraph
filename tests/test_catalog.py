from ecomm_agent.core.config import settings
from ecomm_agent.services.catalog import load_catalog


def test_catalog_has_expected_minimum_size() -> None:
    catalog = load_catalog(settings.catalog_path)
    assert len(catalog) >= 30


def test_catalog_products_include_variants() -> None:
    catalog = load_catalog(settings.catalog_path)
    assert all(product.variants for product in catalog)
