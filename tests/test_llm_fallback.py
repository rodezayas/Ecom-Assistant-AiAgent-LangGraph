import pytest

from ecomm_agent.agents.state import AgentState
from ecomm_agent.services.chatbot import build_reply_text
from ecomm_agent.services.llm import generate_response_text


def _state() -> AgentState:
    return AgentState(
        thread_id="123",
        user_message="Do you have black running shoes under $1500?",
        intent="product_search",
        response_text="Deterministic fallback",
    )


async def _return_none(_: AgentState) -> str | None:
    return None


async def _raise_error(_: AgentState) -> str | None:
    raise RuntimeError("upstream unavailable")


@pytest.mark.anyio
async def test_llm_falls_back_to_groq_when_anthropic_fails(monkeypatch) -> None:
    async def fake_groq(_: AgentState) -> str | None:
        return "Reply from Groq fallback"

    monkeypatch.setattr(
        "ecomm_agent.services.llm._generate_response_text_anthropic",
        _raise_error,
    )
    monkeypatch.setattr(
        "ecomm_agent.services.llm._generate_response_text_groq",
        fake_groq,
    )

    result = await generate_response_text(_state())
    assert result == "Reply from Groq fallback"


@pytest.mark.anyio
async def test_reply_text_falls_back_to_deterministic_when_all_llms_fail(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "ecomm_agent.services.llm._generate_response_text_anthropic",
        _return_none,
    )
    monkeypatch.setattr(
        "ecomm_agent.services.llm._generate_response_text_groq",
        _raise_error,
    )

    result = await build_reply_text(_state())
    assert result == "Deterministic fallback"
