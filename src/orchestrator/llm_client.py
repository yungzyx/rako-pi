"""Cliente de Anthropic Claude.

Wrapper sobre `anthropic.Anthropic` con:
- Modelo y max_tokens configurables (default Haiku 4.5 per arquitectura).
- `cache_control: ephemeral` en el bloque system para reusar prefix
  entre turnos. Si el system prompt no alcanza el mínimo cacheable, no
  cachea silenciosamente — sin error.
- Reintentos delegados al SDK (`max_retries=2` default).
- No usa thinking ni effort (no soportados en Haiku 4.5).

Para tests, el cliente acepta cualquier objeto con un `.messages.create`
compatible — facilita inyectar fakes sin tocar la API real.
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


def _parse_response(response: Any) -> LLMResponse:
    text_parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
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
