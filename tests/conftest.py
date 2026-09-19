import pytest
from httpx import ASGITransport, AsyncClient

from ecomm_agent.api.routes.telegram import clear_seen_updates
from ecomm_agent.main import app


@pytest.fixture(autouse=True)
def _clear_telegram_dedup() -> None:
    clear_seen_updates()
    yield
    clear_seen_updates()


@pytest.fixture
async def async_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
