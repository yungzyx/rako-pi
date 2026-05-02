"""Tests del cliente de Anthropic Claude."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from orchestrator.llm_client import AnthropicLLMClient, LLMClient, LLMResponse
from orchestrator.types import UserContext
from rag.types import Chunk


@dataclass
class _FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 25
    cache_read_input_tokens: int = 80
    cache_creation_input_tokens: int = 20


@dataclass
class _FakeBlock:
    type: str
    text: str = ""


@dataclass
class _FakeMessage:
    content: list[_FakeBlock]
    usage: _FakeUsage = field(default_factory=_FakeUsage)
    stop_reason: str = "end_turn"


@dataclass
class _RecordedCall:
    model: str
    max_tokens: int
    system: list[dict[str, Any]] | str
    messages: list[dict[str, Any]]


class _FakeMessagesAPI:
    def __init__(self, response: _FakeMessage) -> None:
        self._response = response
        self.calls: list[_RecordedCall] = []

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(
            _RecordedCall(
                model=kwargs["model"],
                max_tokens=kwargs["max_tokens"],
                system=kwargs.get("system"),
                messages=kwargs["messages"],
            )
        )
        return self._response


class _FakeAnthropic:
    def __init__(self, response: _FakeMessage) -> None:
        self.messages = _FakeMessagesAPI(response)


def _ctx() -> UserContext:
    return UserContext(
        pending_task_count=2,
        recent_completion_count=1,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
    )


def _chunks() -> tuple[Chunk, ...]:
    return (Chunk(id="01#0", text="Respira profundo.", metadata={"categoria": "respiracion"}),)


def test_llm_client_satisfies_protocol() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="ok")])
    fake = _FakeAnthropic(response)

    client: LLMClient = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="You are Rako.",
    )

    assert hasattr(client, "generate")


def test_generate_returns_text_and_token_counts() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="Estoy aquí contigo.")])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )

    result = client.generate(query="hola", chunks=_chunks(), context=_ctx())

    assert isinstance(result, LLMResponse)
    assert result.text == "Estoy aquí contigo."
    assert result.input_tokens == 100
    assert result.output_tokens == 25
    assert result.cache_read_input_tokens == 80


def test_generate_passes_correct_model_and_max_tokens() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="x")])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=512,
        system_prompt="System.",
    )

    client.generate(query="q", chunks=(), context=_ctx())

    call = fake.messages.calls[0]
    assert call.model == "claude-haiku-4-5"
    assert call.max_tokens == 512


def test_generate_applies_cache_control_to_system_prompt() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="x")])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="A large system prompt.",
    )

    client.generate(query="q", chunks=(), context=_ctx())

    call = fake.messages.calls[0]
    # System se pasa como lista de blocks con cache_control en el último.
    assert isinstance(call.system, list)
    assert call.system[-1].get("cache_control") == {"type": "ephemeral"}


def test_generate_concatenates_text_blocks() -> None:
    response = _FakeMessage(
        content=[
            _FakeBlock(type="text", text="parte 1. "),
            _FakeBlock(type="text", text="parte 2."),
        ]
    )
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )

    result = client.generate(query="q", chunks=(), context=_ctx())

    assert result.text == "parte 1. parte 2."


def test_generate_skips_non_text_blocks() -> None:
    response = _FakeMessage(
        content=[
            _FakeBlock(type="thinking", text=""),
            _FakeBlock(type="text", text="solo texto."),
        ]
    )
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )

    result = client.generate(query="q", chunks=(), context=_ctx())

    assert result.text == "solo texto."


def test_generate_user_message_does_not_contain_pii() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="ok")])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )
    ctx = UserContext(
        pending_task_count=2,
        recent_completion_count=1,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
    )

    client.generate(query="hola", chunks=(), context=ctx)

    call = fake.messages.calls[0]
    user_content = call.messages[0]["content"]
    assert "nombre" not in user_content.lower()
    assert "valencia" not in user_content.lower()
    assert "valence" not in user_content.lower()


def test_generate_propagates_query_and_chunks_into_user_message() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="ok")])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )

    client.generate(
        query="me siento mal",
        chunks=_chunks(),
        context=_ctx(),
    )

    call = fake.messages.calls[0]
    user_content = call.messages[0]["content"]
    assert "me siento mal" in user_content
    assert "Respira profundo" in user_content


def test_generate_with_empty_response_raises() -> None:
    response = _FakeMessage(content=[])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )

    with pytest.raises(ValueError):
        client.generate(query="q", chunks=(), context=_ctx())
