from pydantic import BaseModel, Field


class Variant(BaseModel):
    sku: str
    size: str = Field(description="Size label such as S, M, L, or XL.")
    color: str
    stock: int = Field(ge=0)


class Product(BaseModel):
    id: str
    name: str
    category: str
    description: str
    price: float = Field(ge=0)
    variants: list[Variant]
    tags: list[str]
