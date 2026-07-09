"""Tests del cliente de Anthropic Claude."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from orchestrator.llm_client import AnthropicLLMClient, LLMClient, LLMResponse, OpenAILLMClient
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
        self.closed = False

    def close(self) -> None:
        self.closed = True


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


def test_anthropic_client_closes_underlying_client() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="ok")])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )

    client.close()

    assert fake.closed is True


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


class _FakeOpenAIResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeOpenAIHTTPClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> _FakeOpenAIResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return _FakeOpenAIResponse(self._payload)

    def close(self) -> None:
        self.closed = True


def _openai_payload(text: str = "Estoy contigo.") -> dict[str, Any]:
    return {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ]
            }
        ],
        "usage": {
            "input_tokens": 42,
            "output_tokens": 12,
        },
    }


def test_openai_llm_client_satisfies_protocol() -> None:
    client: LLMClient = OpenAILLMClient(
        http_client=_FakeOpenAIHTTPClient(_openai_payload()),
        api_key="openai-test",
        model="gpt-4o-mini",
        max_tokens=128,
        system_prompt="System.",
    )

    assert hasattr(client, "generate")


def test_openai_generate_posts_expected_responses_request() -> None:
    fake = _FakeOpenAIHTTPClient(_openai_payload("Vamos paso a paso."))
    client = OpenAILLMClient(
        http_client=fake,
        api_key="openai-test",
        model="gpt-4o-mini",
        max_tokens=128,
        system_prompt="System.",
        timeout_s=11.0,
    )

    result = client.generate(query="me siento atascado", chunks=_chunks(), context=_ctx())

    call = fake.calls[0]
    assert call["url"] == "https://api.openai.com/v1/responses"
    assert call["headers"]["authorization"] == "Bearer openai-test"
    assert call["json"]["model"] == "gpt-4o-mini"
    assert call["json"]["max_output_tokens"] == 128
    assert call["json"]["input"][0]["role"] == "system"
    assert call["json"]["input"][1]["role"] == "user"
    assert "me siento atascado" in call["json"]["input"][1]["content"]
    assert result.text == "Vamos paso a paso."
    assert result.input_tokens == 42
    assert result.output_tokens == 12


def test_openai_generate_raises_on_empty_text() -> None:
    fake = _FakeOpenAIHTTPClient(_openai_payload(""))
    client = OpenAILLMClient(
        http_client=fake,
        api_key="openai-test",
        model="gpt-4o-mini",
        max_tokens=128,
        system_prompt="System.",
    )

    with pytest.raises(ValueError):
        client.generate(query="q", chunks=(), context=_ctx())


def test_openai_client_closes_underlying_http_client() -> None:
    fake = _FakeOpenAIHTTPClient(_openai_payload())
    client = OpenAILLMClient(
        http_client=fake,
        api_key="openai-test",
        model="gpt-4o-mini",
        max_tokens=128,
        system_prompt="System.",
    )

    client.close()

    assert fake.closed is True


# ---------------------------------------------------------------------------
# Historial como turnos reales user/assistant (fix de seguimiento del hilo)
# ---------------------------------------------------------------------------


def _ctx_with_turns() -> UserContext:
    return UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        conversation_turns=(
            ("quiero estudiar cálculo", "Dale, ¿qué tema?"),
            ("derivadas", "Partamos con la regla de la cadena."),
        ),
    )


def test_openai_sends_prior_turns_as_real_messages() -> None:
    fake = _FakeOpenAIHTTPClient(_openai_payload())
    client = OpenAILLMClient(
        http_client=fake,
        api_key="k",
        model="gpt-4o-mini",
        max_tokens=128,
        system_prompt="System.",
    )

    client.generate(query="¿y ahora?", chunks=(), context=_ctx_with_turns())

    inp = fake.calls[0]["json"]["input"]
    assert [m["role"] for m in inp] == ["system", "user", "assistant", "user", "assistant", "user"]
    assert inp[1]["content"] == "quiero estudiar cálculo"
    assert inp[2]["content"] == "Dale, ¿qué tema?"
    assert "¿y ahora?" in inp[-1]["content"]


def test_anthropic_sends_prior_turns_as_real_messages() -> None:
    response = _FakeMessage(content=[_FakeBlock(type="text", text="ok")])
    fake = _FakeAnthropic(response)
    client = AnthropicLLMClient(
        client=fake,
        model="claude-haiku-4-5",
        max_tokens=128,
        system_prompt="System.",
    )

    client.generate(query="¿y ahora?", chunks=(), context=_ctx_with_turns())

    msgs = fake.messages.calls[0].messages
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    assert msgs[0]["content"] == "quiero estudiar cálculo"
    assert "¿y ahora?" in msgs[-1]["content"]


def test_whole_payload_has_no_pii_across_history_and_current_turn() -> None:
    # El sobre §4.1.3 debe cumplirse en TODO el array de mensajes, no solo en el
    # turno actual: sin nombre, sin vector emocional crudo.
    fake = _FakeOpenAIHTTPClient(_openai_payload())
    client = OpenAILLMClient(
        http_client=fake,
        api_key="k",
        model="gpt-4o-mini",
        max_tokens=128,
        system_prompt="System.",
    )

    client.generate(query="hola", chunks=(), context=_ctx_with_turns())

    whole = " ".join(m["content"] for m in fake.calls[0]["json"]["input"]).lower()
    assert "nombre" not in whole
    assert "valencia" not in whole
    assert "valence" not in whole


def test_history_turns_are_passed_through_within_truncation_envelope() -> None:
    # El builder no infla el historial: los turnos vienen ya truncados (180) de
    # ConversationMemory y se pasan tal cual, sin exceder ese sobre.
    truncated = "a" * 180
    ctx = UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        conversation_turns=((truncated, truncated),),
    )
    fake = _FakeOpenAIHTTPClient(_openai_payload())
    client = OpenAILLMClient(
        http_client=fake,
        api_key="k",
        model="gpt-4o-mini",
        max_tokens=128,
        system_prompt="System.",
    )

    client.generate(query="hola", chunks=(), context=ctx)

    inp = fake.calls[0]["json"]["input"]
    assert inp[1]["content"] == truncated and len(inp[1]["content"]) <= 180
    assert inp[2]["content"] == truncated and len(inp[2]["content"]) <= 180
