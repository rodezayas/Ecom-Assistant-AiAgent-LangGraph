import pytest


@pytest.mark.anyio
async def test_app_starts_without_webhook_configuration(async_client) -> None:
    response = await async_client.get("/health")
    assert response.status_code == 200
