"""Orquestador — decisión central por turno.

Flujo:
1. Construir `CrisisInput` y consultar `safety.detector` PRIMERO.
2. Si hay crisis → bypassear LLM, ejecutar protocolo curado.
3. Si NONE/ELEVATED → consultar RAG + Claude.
4. Devolver un `TurnResult` con todo lo que el resto del sistema
   necesita para despachar (texto, audio path, LEDs, eventos).

El orquestador NO toca hardware ni cloud directamente; recibe sus
colaboradores por construcción y se mantiene determinístico para tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from emotion.types import EmotionalVector
from orchestrator.llm_client import LLMClient
from orchestrator.types import UserContext
from rag.client import Retriever
from safety.detector import detect_crisis
from safety.protocol import CrisisProtocol
from safety.responses import pick_response
from safety.scope import (
    build_elevated_support_response,
    build_scope_redirect_response,
    mentions_mental_health_topic,
)
from safety.types import (
    CrisisInput,
    CrisisLevel,
    CrisisSignal,
    EmotionalSample,
    PanicSource,
)

_RAG_TOP_K = 5
_RAG_MAX_QUERY_LEN = 500


class TurnKind(Enum):
    LLM_RESPONSE = "LLM_RESPONSE"
    CRISIS_PROTOCOL = "CRISIS_PROTOCOL"
    SCOPE_REDIRECT = "SCOPE_REDIRECT"
    ELEVATED_SUPPORT = "ELEVATED_SUPPORT"


@dataclass(frozen=True, slots=True)
class TurnInput:
    transcript: str
    emotion: EmotionalVector | None
    panic_button: PanicSource | None
    emotion_history: tuple[EmotionalSample, ...]
    last_high_distress_at: datetime | None
    last_interaction_at: datetime | None
    user_context: UserContext
    now: datetime


@dataclass(frozen=True, slots=True)
class TurnResult:
    kind: TurnKind
    text: str
    audio_path: str | None
    rag_chunk_ids: tuple[str, ...]
    notify_contact: bool
    show_resources: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLMClient,
        protocol: CrisisProtocol,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._protocol = protocol

    def handle_turn(self, input: TurnInput) -> TurnResult:
        signal = self._detect(input)

        if signal.should_bypass_llm:
            return self._handle_crisis(signal)
        if mentions_mental_health_topic(input.transcript):
            return self._handle_scope_redirect()
        if signal.level is CrisisLevel.ELEVATED:
            return self._handle_elevated_support()

        return self._handle_llm_turn(input, signal)

    def _detect(self, input: TurnInput) -> CrisisSignal:
        crisis_input = CrisisInput(
            transcript=input.transcript,
            emotion_history=input.emotion_history,
            panic_button=input.panic_button,
            last_high_distress_at=input.last_high_distress_at,
            last_interaction_at=input.last_interaction_at,
            now=input.now,
        )
        return detect_crisis(crisis_input)

    def _handle_crisis(self, signal: CrisisSignal) -> TurnResult:
        outcome = self._protocol.execute(signal)
        response = pick_response(signal)
        return TurnResult(
            kind=TurnKind.CRISIS_PROTOCOL,
            text=response.text,
            audio_path=response.audio_path,
            rag_chunk_ids=(),
            notify_contact=outcome.notified_trusted_contact,
            show_resources=True,
            metadata={
                "reasons": tuple(r.name for r in signal.reasons),
                "response_id": outcome.response_id,
            },
        )

    def _handle_scope_redirect(self) -> TurnResult:
        return TurnResult(
            kind=TurnKind.SCOPE_REDIRECT,
            text=build_scope_redirect_response(),
            audio_path=None,
            rag_chunk_ids=(),
            notify_contact=False,
            show_resources=True,
            metadata={"reason": "mental_health_scope"},
        )

    def _handle_elevated_support(self) -> TurnResult:
        return TurnResult(
            kind=TurnKind.ELEVATED_SUPPORT,
            text=build_elevated_support_response(),
            audio_path=None,
            rag_chunk_ids=(),
            notify_contact=False,
            show_resources=True,
            metadata={"elevated": True},
        )

    def _handle_llm_turn(self, input: TurnInput, signal: CrisisSignal) -> TurnResult:
        query = input.transcript[:_RAG_MAX_QUERY_LEN]
        chunks = self._retriever.query(query, top_k=_RAG_TOP_K)
        llm_response = self._llm.generate(
            query=input.transcript,
            chunks=chunks,
            context=input.user_context,
        )
        return TurnResult(
            kind=TurnKind.LLM_RESPONSE,
            text=llm_response.text,
            audio_path=None,
            rag_chunk_ids=tuple(c.id for c in chunks),
            notify_contact=False,
            show_resources=False,
            metadata={
                "elevated": signal.level is CrisisLevel.ELEVATED,
                "input_tokens": llm_response.input_tokens,
                "output_tokens": llm_response.output_tokens,
                "cache_read_input_tokens": llm_response.cache_read_input_tokens,
            },
        )
