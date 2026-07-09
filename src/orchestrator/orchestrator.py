"""Orquestador — decisión central por turno.

Flujo:
1. Construir `CrisisInput` y consultar `safety.detector` PRIMERO.
2. Si hay crisis → bypassear LLM, ejecutar protocolo curado.
3. Si no hay crisis → `safety.triage` diferencia el caso: consejo clínico
   (redirección), revelación personal o patrón recurrente (derivación a
   la unidad de bienestar), estrés académico (LLM con nota de tono), o
   conversación normal (LLM).
4. Devolver un `TurnResult` con todo lo que el resto del sistema
   necesita para despachar (texto, audio path, LEDs, eventos).

El orquestador NO toca hardware ni cloud directamente; recibe sus
colaboradores por construcción y se mantiene determinístico para tests.
Si el LLM o el RAG fallan en runtime, el turno degrada a una respuesta
curada breve — nunca silencio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from emotion.types import EmotionalVector
from orchestrator.llm_client import LLMClient, LLMResponse
from orchestrator.memory import is_near_repeat
from orchestrator.types import UserContext
from rag.client import Retriever
from rag.types import Chunk
from safety.detector import detect_crisis
from safety.protocol import CrisisProtocol
from safety.responses import pick_response
from safety.scope import (
    build_crisis_aftercare_response,
    build_elevated_support_response,
    build_scope_redirect_response,
    build_wellbeing_referral_response,
)
from safety.triage import TriageLevel, TriageResult, triage_turn
from safety.types import (
    CrisisInput,
    CrisisLevel,
    CrisisSignal,
    EmotionalSample,
    PanicSource,
)

_log = logging.getLogger(__name__)

_RAG_TOP_K = 5
_RAG_MAX_QUERY_LEN = 500

# Ventana de "aftercare" tras una crisis: durante este lapso, cualquier turno
# que NO sea una nueva crisis se queda en presencia + derivación curada, sin
# LLM ni coaching de productividad. Es la corrección a un hueco real de
# seguridad: hoy el pipeline evalúa cada turno en aislamiento, así que el
# turno siguiente a "ya no quiero vivir" —si no repite palabras clave— caía al
# LLM y respondía "abre tu libro de cálculo". La crisis fresca SIEMPRE se
# atiende primero (bypass del detector); esto solo cubre los turnos de después.
_AFTERCARE_WINDOW = timedelta(minutes=45)

# Respuesta curada cuando el LLM falla en runtime (red caída, API con
# error). Corta, honesta, sin fingir que entendió.
_LLM_FALLBACK_TEXT = (
    "Se me cortó la conexión un momento y no quiero inventarte una respuesta. "
    "¿Me lo repites en un ratito?"
)

# Nota de tono que acompaña un turno con estrés académico detectado.
# Instrucción fija: no lleva datos del usuario al LLM.
_SUPPORT_HINT = (
    "El usuario expresó una emoción difícil (nervios, estrés, ánimo bajo o "
    "pocas ganas) en su día a día. Primero valida lo que siente con calidez y "
    "sin minimizar. Solo después, y solo si encaja, ofrece UN paso pequeño, "
    "amable y opcional — nunca una lista ni presión. No diagnostiques ni des "
    "consejos clínicos."
)

# Instrucción de reformulación cuando el LLM generó casi lo mismo que ya
# dijo en esta sesión. Un solo reintento — si insiste, se acepta.
_VARY_HINT = (
    "Tu borrador anterior era casi idéntico a algo que ya dijiste en esta "
    "conversación. Reformula con otra estructura y aporta un ángulo o paso "
    "distinto, sin repetir la misma apertura ni el mismo cierre."
)


class TurnKind(Enum):
    LLM_RESPONSE = "LLM_RESPONSE"
    CRISIS_PROTOCOL = "CRISIS_PROTOCOL"
    CRISIS_AFTERCARE = "CRISIS_AFTERCARE"
    SCOPE_REDIRECT = "SCOPE_REDIRECT"
    ELEVATED_SUPPORT = "ELEVATED_SUPPORT"
    WELLBEING_REFERRAL = "WELLBEING_REFERRAL"
    LLM_FALLBACK = "LLM_FALLBACK"


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
    # Señales para el triage no-crisis (ver safety/triage.py). Con los
    # defaults el comportamiento es el conservador (sin recurrencia, sin
    # unidad de bienestar configurada).
    recent_low_mood_days: int = 0
    wellbeing_unit_name: str | None = None
    wellbeing_unit_phone: str | None = None
    # Última crisis real registrada (journal). Si es reciente (< ventana de
    # aftercare) los turnos de seguimiento no vuelven al LLM. None = sin
    # crisis reciente (default conservador).
    recent_crisis_at: datetime | None = None


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

        # Aftercare post-crisis: si hubo una crisis real hace poco y este
        # turno no es una nueva crisis, NO volvemos al LLM ni a coaching de
        # estudio — presencia y derivación. Va antes que el triage porque
        # domina todo salvo una crisis fresca (ya descartada arriba).
        if self._in_aftercare_window(input):
            return self._handle_aftercare()

        triage = triage_turn(
            input.transcript,
            recent_low_mood_days=input.recent_low_mood_days,
            elevated=signal.level is CrisisLevel.ELEVATED,
        )
        if triage.level is TriageLevel.CLINICAL_SCOPE:
            return self._handle_scope_redirect(triage)
        if triage.level is TriageLevel.WELLBEING_REFERRAL:
            return self._handle_wellbeing_referral(input, triage)
        if triage.level is TriageLevel.ELEVATED_SUPPORT:
            return self._handle_elevated_support()

        supportive = triage.level is TriageLevel.SUPPORTIVE_ACADEMIC
        return self._handle_llm_turn(input, signal, supportive=supportive)

    def close(self) -> None:
        for resource in (self._retriever, self._llm):
            close = getattr(resource, "close", None)
            if callable(close):
                close()

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

    def _in_aftercare_window(self, input: TurnInput) -> bool:
        """True si hubo una crisis real dentro de la ventana de aftercare.

        Los turnos de seguimiento a una crisis deben quedarse en presencia +
        derivación, nunca en el LLM. Blindado contra timestamps futuros
        (delta negativo → fuera de ventana)."""
        if input.recent_crisis_at is None:
            return False
        elapsed = input.now - input.recent_crisis_at
        return timedelta(0) <= elapsed <= _AFTERCARE_WINDOW

    def _handle_aftercare(self) -> TurnResult:
        return TurnResult(
            kind=TurnKind.CRISIS_AFTERCARE,
            text=build_crisis_aftercare_response(),
            audio_path=None,
            rag_chunk_ids=(),
            notify_contact=False,  # ya se alertó en la crisis; no re-spamear
            show_resources=True,
            metadata={"reason": "post_crisis_aftercare"},
        )

    def _handle_scope_redirect(self, triage: TriageResult) -> TurnResult:
        return TurnResult(
            kind=TurnKind.SCOPE_REDIRECT,
            text=build_scope_redirect_response(),
            audio_path=None,
            rag_chunk_ids=(),
            notify_contact=False,
            show_resources=True,
            metadata={"reason": "mental_health_scope", "triage": triage.reason},
        )

    def _handle_wellbeing_referral(self, input: TurnInput, triage: TriageResult) -> TurnResult:
        return TurnResult(
            kind=TurnKind.WELLBEING_REFERRAL,
            text=build_wellbeing_referral_response(
                unit_name=input.wellbeing_unit_name,
                unit_phone=input.wellbeing_unit_phone,
            ),
            audio_path=None,
            rag_chunk_ids=(),
            notify_contact=False,
            show_resources=True,
            metadata={"reason": "wellbeing_referral", "triage": triage.reason},
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

    def _handle_llm_turn(
        self,
        input: TurnInput,
        signal: CrisisSignal,
        *,
        supportive: bool = False,
    ) -> TurnResult:
        chunks = self._safe_chunks(input.transcript)
        context = input.user_context
        if supportive:
            context = replace(context, support_hint=_SUPPORT_HINT)
        try:
            llm_response, retried = self._generate_avoiding_repeats(input, chunks, context)
        except Exception:
            _log.exception("LLM generation failed; returning curated fallback")
            return self._llm_fallback()
        return TurnResult(
            kind=TurnKind.LLM_RESPONSE,
            text=llm_response.text,
            audio_path=None,
            rag_chunk_ids=tuple(c.id for c in chunks),
            notify_contact=False,
            show_resources=False,
            metadata={
                "elevated": signal.level is CrisisLevel.ELEVATED,
                "supportive": supportive,
                "repeat_retry": retried,
                "input_tokens": llm_response.input_tokens,
                "output_tokens": llm_response.output_tokens,
                "cache_read_input_tokens": llm_response.cache_read_input_tokens,
            },
        )

    def _generate_avoiding_repeats(
        self,
        input: TurnInput,
        chunks: tuple[Chunk, ...],
        context: UserContext,
    ) -> tuple[LLMResponse, bool]:
        """Genera; si el texto repite algo ya dicho, reintenta UNA vez.

        El segundo intento lleva una instrucción de reformulación. Si el
        reintento falla con excepción, se conserva la primera respuesta —
        repetirse es mejor que quedarse callado.
        """
        response = self._llm.generate(query=input.transcript, chunks=chunks, context=context)
        recent = input.user_context.recent_conversation
        if not is_near_repeat(response.text, recent):
            return response, False
        vary_hint = f"{context.support_hint} {_VARY_HINT}" if context.support_hint else _VARY_HINT
        try:
            retry = self._llm.generate(
                query=input.transcript,
                chunks=chunks,
                context=replace(context, support_hint=vary_hint),
            )
        except Exception:
            _log.exception("vary retry failed; keeping first response")
            return response, True
        return retry, True

    def _safe_chunks(self, transcript: str) -> tuple[Chunk, ...]:
        """RAG caído no debe botar el turno — degrada a cero chunks."""
        query = transcript[:_RAG_MAX_QUERY_LEN]
        try:
            return tuple(self._retriever.query(query, top_k=_RAG_TOP_K))
        except Exception:
            _log.exception("RAG query failed; continuing without chunks")
            return ()

    def _llm_fallback(self) -> TurnResult:
        return TurnResult(
            kind=TurnKind.LLM_FALLBACK,
            text=_LLM_FALLBACK_TEXT,
            audio_path=None,
            rag_chunk_ids=(),
            notify_contact=False,
            show_resources=False,
            metadata={"reason": "llm_error"},
        )
