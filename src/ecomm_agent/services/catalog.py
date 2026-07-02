import json
from pathlib import Path

from ecomm_agent.schemas.catalog import Product


def load_catalog(path: str) -> list[Product]:
    catalog_path = Path(path)
    if not catalog_path.exists():
        return []
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return [Product.model_validate(item) for item in data]
