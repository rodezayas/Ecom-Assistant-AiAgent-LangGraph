import pytest

from ecomm_agent.agents.state import AgentState


@pytest.mark.anyio
async def test_telegram_webhook_sends_generated_reply(monkeypatch, async_client) -> None:
    async def fake_build_reply_text(state: AgentState) -> str:
        assert state.thread_id == "12345"
        return "Verified reply from Anthropic path"

    async def fake_send_text_message(chat_id: int, text: str) -> dict:
        assert chat_id == 12345
        assert text == "Verified reply from Anthropic path"
        return {"ok": True, "result": {"message_id": 777}}

    monkeypatch.setattr(
        "ecomm_agent.api.routes.telegram.build_reply_text",
        fake_build_reply_text,
    )
    monkeypatch.setattr(
        "ecomm_agent.api.routes.telegram.send_text_message",
        fake_send_text_message,
    )

    response = await async_client.post(
        "/webhook/telegram",
        json={
            "update_id": 1,
            "message": {
                "message_id": 99,
                "chat": {"id": 12345},
                "text": "do you have black running shoes under 1500?",
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["telegram_sent"] is True
    assert response.json()["telegram_message_id"] == 777
    assert response.json()["response_text"] == "Verified reply from Anthropic path"
    assert response.json()["telegram_error"] is None


@pytest.mark.anyio
async def test_telegram_webhook_ignores_empty_messages(async_client) -> None:
    response = await async_client.post(
        "/webhook/telegram",
        json={
            "update_id": 1,
            "message": {
                "message_id": 99,
                "chat": {"id": 12345},
                "text": "",
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["telegram_sent"] is False


@pytest.mark.anyio
async def test_telegram_webhook_handles_send_failures(monkeypatch, async_client) -> None:
    async def fake_build_reply_text(_: AgentState) -> str:
        return "Fallback reply"

    async def fake_send_text_message(chat_id: int, text: str) -> dict:
        assert chat_id == 12345
        assert text == "Fallback reply"
        raise RuntimeError("telegram send failed")

    monkeypatch.setattr(
        "ecomm_agent.api.routes.telegram.build_reply_text",
        fake_build_reply_text,
    )
    monkeypatch.setattr(
        "ecomm_agent.api.routes.telegram.send_text_message",
        fake_send_text_message,
    )

    response = await async_client.post(
        "/webhook/telegram",
        json={
            "update_id": 1,
            "message": {
                "message_id": 99,
                "chat": {"id": 12345},
                "text": "hello",
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["telegram_sent"] is False
    assert response.json()["telegram_message_id"] is None
    assert response.json()["telegram_error"] == "telegram send failed"
