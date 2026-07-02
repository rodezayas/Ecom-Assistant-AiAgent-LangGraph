import pytest
from httpx import ASGITransport, AsyncClient

from ecomm_agent.main import app


@pytest.fixture
async def async_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
