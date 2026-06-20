"""Clientes LLM.

Wrappers de proveedores cloud con el mismo `LLMClient`:
- `OpenAILLMClient` usa Responses API y es el default barato/rápido.
- `AnthropicLLMClient` mantiene Claude como alternativa/fallback.
- Modelo y max_tokens configurables.
- `cache_control: ephemeral` en el bloque system para reusar prefix
  entre turnos de Anthropic. Si el system prompt no alcanza el mínimo
  cacheable, no cachea silenciosamente — sin error.

Para tests, ambos clientes aceptan objetos fake inyectados sin tocar APIs reales.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from orchestrator.prompts import build_user_message
from orchestrator.types import UserContext
from rag.types import Chunk


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class LLMClient(Protocol):
    def generate(
        self,
        query: str,
        chunks: tuple[Chunk, ...],
        context: UserContext,
    ) -> LLMResponse: ...


class AnthropicLLMClient:
    """Implementación concreta sobre `anthropic.Anthropic`."""

    def __init__(
        self,
        client: Any,
        *,
        model: str,
        max_tokens: int,
        system_prompt: str,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt

    def generate(
        self,
        query: str,
        chunks: tuple[Chunk, ...],
        context: UserContext,
    ) -> LLMResponse:
        user_message = build_user_message(query, chunks, context)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )
        return _parse_response(response)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


class OpenAILLMClient:
    """Implementación concreta sobre OpenAI Responses API."""

    def __init__(
        self,
        http_client: Any,
        *,
        api_key: str,
        model: str,
        max_tokens: int,
        system_prompt: str,
        timeout_s: float = 15.0,
    ) -> None:
        self._http = http_client
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt
        self._timeout_s = timeout_s

    def generate(
        self,
        query: str,
        chunks: tuple[Chunk, ...],
        context: UserContext,
    ) -> LLMResponse:
        user_message = build_user_message(query, chunks, context)
        response = self._http.post(
            "https://api.openai.com/v1/responses",
            headers={
                "authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            },
            json={
                "model": self._model,
                "max_output_tokens": self._max_tokens,
                "input": [
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        return _parse_openai_response(response.json())

    def close(self) -> None:
        close = getattr(self._http, "close", None)
        if callable(close):
            close()


def _parse_response(response: Any) -> LLMResponse:
    text_parts = [
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ]
    text = "".join(text_parts).strip()
    if not text:
        raise ValueError("LLM response contained no text blocks")

    usage = response.usage
    return LLMResponse(
        text=text,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0),
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0),
    )


def _parse_openai_response(payload: dict[str, Any]) -> LLMResponse:
    text_parts: list[str] = []
    for item in payload.get("output", []):
        for block in item.get("content", []):
            if block.get("type") == "output_text":
                text_parts.append(str(block.get("text", "")))

    text = "".join(text_parts).strip()
    if not text:
        raise ValueError("LLM response contained no text blocks")

    usage = payload.get("usage", {})
    return LLMResponse(
        text=text,
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
