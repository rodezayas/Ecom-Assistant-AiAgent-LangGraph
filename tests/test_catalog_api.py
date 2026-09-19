import pytest


@pytest.mark.anyio
async def test_catalog_list_returns_products(async_client) -> None:
    response = await async_client.get("/api/catalog")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body
    assert body[0]["id"] == "TSH-001"
    assert "variants" in body[0]


@pytest.mark.anyio
async def test_catalog_product_returns_existing_product(async_client) -> None:
    response = await async_client.get("/api/catalog/TSH-001")

    assert response.status_code == 200
    assert response.json()["id"] == "TSH-001"
    assert response.json()["name"] == "Aster Core Tee"


@pytest.mark.anyio
async def test_catalog_product_returns_404_for_missing_id(async_client) -> None:
    response = await async_client.get("/api/catalog/DOES-NOT-EXIST")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found."}


@pytest.mark.anyio
async def test_catalog_product_rejects_post(async_client) -> None:
    response = await async_client.post("/api/catalog/TSH-001")

    assert response.status_code == 405


@pytest.mark.anyio
async def test_catalog_cors_allows_lovable_origin(async_client) -> None:
    response = await async_client.options(
        "/api/catalog/TSH-001",
        headers={
            "Origin": "https://demo.lovable.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://demo.lovable.app"
    assert "GET" in response.headers["access-control-allow-methods"]
