"""Tests del orquestador — decisión central por turno."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from emotion.types import EmotionalVector
from rag.types import Chunk
from safety.types import (
    CrisisInput,
    CrisisLevel,
    CrisisReason,
    CrisisSignal,
    EmotionalSample,
    PanicSource,
)

from orchestrator.llm_client import LLMResponse
from orchestrator.orchestrator import Orchestrator, TurnInput, TurnResult, TurnKind
from orchestrator.types import UserContext

UTC = timezone.utc


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeRetriever:
    chunks: tuple[Chunk, ...] = ()
    queries: list[str] = field(default_factory=list)

    def query(self, text: str, top_k: int = 5, where=None) -> tuple[Chunk, ...]:
        self.queries.append(text)
        return self.chunks


@dataclass
class _FakeLLMClient:
    response_text: str = "Estoy contigo. ¿Qué tal una pausa breve?"
    calls: list[tuple[str, tuple[Chunk, ...]]] = field(default_factory=list)

    def generate(
        self,
        query: str,
        chunks: tuple[Chunk, ...],
        context: UserContext,
    ) -> LLMResponse:
        self.calls.append((query, chunks))
        return LLMResponse(
            text=self.response_text,
            input_tokens=120,
            output_tokens=24,
            cache_read_input_tokens=100,
            cache_creation_input_tokens=20,
        )


@dataclass
class _FakeProtocolVoice:
    played: list[str] = field(default_factory=list)

    def play_prerecorded(self, response_id: str) -> None:
        self.played.append(response_id)


@dataclass
class _FakeProtocolLighting:
    present_set: int = 0

    def set_present_state(self) -> None:
        self.present_set += 1


@dataclass
class _FakeProtocolNotifier:
    contacts_notified: list[CrisisSignal] = field(default_factory=list)
    resources_shown: int = 0

    def notify_trusted_contact(self, signal: CrisisSignal) -> None:
        self.contacts_notified.append(signal)

    def show_resources(self) -> None:
        self.resources_shown += 1


@dataclass
class _FakeProtocolJournal:
    entries: list[CrisisSignal] = field(default_factory=list)

    def record(self, signal: CrisisSignal) -> None:
        self.entries.append(signal)


def _build_orchestrator(
    *,
    retriever: _FakeRetriever | None = None,
    llm: _FakeLLMClient | None = None,
) -> tuple[Orchestrator, _FakeRetriever, _FakeLLMClient, _FakeProtocolJournal]:
    from safety.protocol import CrisisProtocol

    voice = _FakeProtocolVoice()
    lighting = _FakeProtocolLighting()
    notifier = _FakeProtocolNotifier()
    journal = _FakeProtocolJournal()
    protocol = CrisisProtocol(voice=voice, lighting=lighting, notifier=notifier, journal=journal)

    retriever = retriever or _FakeRetriever(
        chunks=(Chunk(id="x#0", text="técnica relevante", metadata={}),)
    )
    llm = llm or _FakeLLMClient()

    orch = Orchestrator(
        retriever=retriever,
        llm=llm,
        protocol=protocol,
    )
    return orch, retriever, llm, journal


def _ctx() -> UserContext:
    return UserContext(
        pending_task_count=2,
        recent_completion_count=1,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
    )


def _input(**overrides) -> TurnInput:
    base = dict(
        transcript="me siento atascado",
        emotion=None,
        panic_button=None,
        emotion_history=(),
        last_high_distress_at=None,
        last_interaction_at=_now(),
        user_context=_ctx(),
        now=_now(),
    )
    base.update(overrides)
    return TurnInput(**base)


# ---------------------------------------------------------------------------
# Decisiones
# ---------------------------------------------------------------------------


def test_normal_flow_consults_rag_then_llm() -> None:
    orch, retriever, llm, _ = _build_orchestrator()

    result = orch.handle_turn(_input())

    assert isinstance(result, TurnResult)
    assert result.kind is TurnKind.LLM_RESPONSE
    assert "Estoy contigo" in result.text
    assert retriever.queries == ["me siento atascado"]
    assert len(llm.calls) == 1


def test_panic_button_bypasses_llm() -> None:
    orch, retriever, llm, journal = _build_orchestrator()

    result = orch.handle_turn(_input(panic_button=PanicSource.PHYSICAL))

    assert result.kind is TurnKind.CRISIS_PROTOCOL
    assert llm.calls == []  # LLM no fue invocado
    assert retriever.queries == []  # RAG no fue consultado tampoco
    assert len(journal.entries) == 1
    assert result.notify_contact is True
    assert result.show_resources is True


def test_ideation_keywords_bypass_llm() -> None:
    orch, _, llm, journal = _build_orchestrator()

    result = orch.handle_turn(_input(transcript="quiero morir"))

    assert result.kind is TurnKind.CRISIS_PROTOCOL
    assert llm.calls == []
    assert len(journal.entries) == 1


def test_sustained_emotional_extreme_bypasses_llm() -> None:
    history = tuple(
        EmotionalSample(
            vector=EmotionalVector(valence=-0.85, arousal=0.85, dominance=0.5),
            at=_now(),
        )
        for _ in range(5)
    )
    # Spread samples in time
    history = tuple(
        EmotionalSample(
            vector=h.vector,
            at=_now().replace(minute=18 - i * 2),
        )
        for i, h in enumerate(history)
    )

    orch, _, llm, journal = _build_orchestrator()

    result = orch.handle_turn(_input(emotion_history=history))

    assert result.kind is TurnKind.CRISIS_PROTOCOL
    assert llm.calls == []
    assert len(journal.entries) == 1


def test_elevated_emotional_state_does_not_bypass_but_is_noted() -> None:
    from datetime import timedelta

    history = tuple(
        EmotionalSample(
            vector=EmotionalVector(valence=-0.55, arousal=0.6, dominance=0.5),
            at=_now() - timedelta(minutes=m),
        )
        for m in (40, 30, 20, 10, 0)
    )
    orch, _, llm, _ = _build_orchestrator()

    result = orch.handle_turn(_input(emotion_history=history))

    assert result.kind is TurnKind.LLM_RESPONSE
    assert len(llm.calls) == 1
    assert result.metadata.get("elevated") is True


def test_turn_result_carries_chunk_ids_for_traceability() -> None:
    chunks = (
        Chunk(id="01#0", text="x", metadata={}),
        Chunk(id="02#0", text="y", metadata={}),
    )
    orch, _, _, _ = _build_orchestrator(retriever=_FakeRetriever(chunks=chunks))

    result = orch.handle_turn(_input())

    assert result.rag_chunk_ids == ("01#0", "02#0")


def test_crisis_result_carries_response_audio_path() -> None:
    orch, _, _, _ = _build_orchestrator()

    result = orch.handle_turn(_input(panic_button=PanicSource.APP))

    assert result.audio_path is not None
    assert result.audio_path.endswith(".wav")


def test_normal_result_has_no_pre_rendered_audio_path() -> None:
    orch, _, _, _ = _build_orchestrator()

    result = orch.handle_turn(_input())

    assert result.audio_path is None  # TTS rendera en vivo


def test_handle_turn_is_pure_for_same_input() -> None:
    # Determinismo: dos llamadas con el mismo input + fakes determinísticos
    # producen el mismo resultado (importante para reproducibilidad).
    orch1, _, _, _ = _build_orchestrator()
    orch2, _, _, _ = _build_orchestrator()

    r1 = orch1.handle_turn(_input())
    r2 = orch2.handle_turn(_input())

    assert r1.kind == r2.kind
    assert r1.text == r2.text
    assert r1.rag_chunk_ids == r2.rag_chunk_ids
