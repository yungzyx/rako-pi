"""Tests del orquestador — decisión central por turno."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from emotion.types import EmotionalVector
from orchestrator.llm_client import LLMResponse
from orchestrator.orchestrator import Orchestrator, TurnInput, TurnKind, TurnResult
from orchestrator.types import UserContext
from rag.types import Chunk
from safety.types import (
    CrisisSignal,
    EmotionalSample,
    PanicSource,
)

UTC = UTC


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
    contexts: list[UserContext] = field(default_factory=list)

    def generate(
        self,
        query: str,
        chunks: tuple[Chunk, ...],
        context: UserContext,
    ) -> LLMResponse:
        self.calls.append((query, chunks))
        self.contexts.append(context)
        return LLMResponse(
            text=self.response_text,
            input_tokens=120,
            output_tokens=24,
            cache_read_input_tokens=100,
            cache_creation_input_tokens=20,
        )


@dataclass
class _ExplodingLLMClient:
    def generate(self, query, chunks, context) -> LLMResponse:  # type: ignore[no-untyped-def]
        raise RuntimeError("API down")


@dataclass
class _ExplodingRetriever:
    def query(self, text: str, top_k: int = 5, where=None):  # type: ignore[no-untyped-def]
        raise RuntimeError("chroma down")


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
    from datetime import timedelta

    history = tuple(
        EmotionalSample(
            vector=EmotionalVector(valence=-0.85, arousal=0.85, dominance=0.5),
            at=_now() - timedelta(minutes=m),
        )
        for m in (8, 6, 4, 2, 0)
    )

    orch, _, llm, journal = _build_orchestrator()

    result = orch.handle_turn(_input(emotion_history=history))

    assert result.kind is TurnKind.CRISIS_PROTOCOL
    assert llm.calls == []
    assert len(journal.entries) == 1


def test_elevated_emotional_state_uses_curated_support_not_llm() -> None:
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

    assert result.kind is TurnKind.ELEVATED_SUPPORT
    assert len(llm.calls) == 0
    assert result.metadata.get("elevated") is True
    assert "Bienestar UDD" in result.text


def test_personal_disclosure_refers_to_wellbeing_without_llm() -> None:
    # Cambio deliberado (Fase 1): "creo que tengo ansiedad" ya no recibe la
    # redirección fría "supera mi rol" — es una revelación personal y merece
    # una derivación cálida a bienestar. Sigue sin tocar el LLM.
    orch, retriever, llm, _ = _build_orchestrator()

    result = orch.handle_turn(_input(transcript="creo que tengo ansiedad"))

    assert result.kind is TurnKind.WELLBEING_REFERRAL
    assert llm.calls == []
    assert retriever.queries == []
    assert "Bienestar UDD" in result.text  # nombra la unidad, no el número
    assert "+56 2 2820 3419" not in result.text
    assert result.show_resources is True


def test_help_seeking_refers_to_wellbeing_without_llm() -> None:
    orch, retriever, llm, _ = _build_orchestrator()

    result = orch.handle_turn(_input(transcript="necesito terapia por trauma"))

    assert result.kind is TurnKind.WELLBEING_REFERRAL
    assert llm.calls == []
    assert retriever.queries == []


def test_wellbeing_referral_uses_configured_unit_when_available() -> None:
    orch, _, llm, _ = _build_orchestrator()

    result = orch.handle_turn(
        _input(
            transcript="necesito un psicólogo",
            wellbeing_unit_name="Bienestar UDD",
            wellbeing_unit_phone="+56 2 2820 3419",
        )
    )

    assert result.kind is TurnKind.WELLBEING_REFERRAL
    assert "Bienestar UDD" in result.text  # nombra la unidad configurada
    assert "+56 2 2820 3419" not in result.text  # sin recitar el número
    assert "WhatsApp" in result.text
    assert llm.calls == []


def test_clinical_advice_request_redirects_without_llm() -> None:
    orch, retriever, llm, _ = _build_orchestrator()

    result = orch.handle_turn(_input(transcript="¿qué medicamento debería tomar?"))

    assert result.kind is TurnKind.SCOPE_REDIRECT
    assert "supera mi rol" in result.text
    assert llm.calls == []
    assert retriever.queries == []


def test_academic_stress_mention_goes_to_llm_with_support_hint() -> None:
    # Cambio deliberado (Fase 1): mencionar ansiedad por una prueba ya no
    # redirige en frío — el LLM acompaña, con una nota de tono fija.
    orch, _, llm, _ = _build_orchestrator()

    result = orch.handle_turn(_input(transcript="tengo ansiedad por la prueba de mañana"))

    assert result.kind is TurnKind.LLM_RESPONSE
    assert len(llm.calls) == 1
    assert llm.contexts[0].support_hint is not None
    assert result.metadata["supportive"] is True


def test_normal_turn_carries_no_support_hint() -> None:
    orch, _, llm, _ = _build_orchestrator()

    orch.handle_turn(_input(transcript="quiero estudiar cálculo 25 minutos"))

    assert llm.contexts[0].support_hint is None


def test_recurring_low_mood_upgrades_stress_mention_to_referral() -> None:
    orch, _, llm, _ = _build_orchestrator()

    result = orch.handle_turn(
        _input(
            transcript="tengo ansiedad por la prueba de mañana",
            recent_low_mood_days=4,
        )
    )

    assert result.kind is TurnKind.WELLBEING_REFERRAL
    assert llm.calls == []


def test_repeated_llm_response_triggers_one_vary_retry() -> None:
    repeated = "Partamos con un bloque corto de 25 minutos de cálculo."
    llm = _FakeLLMClient(response_text=repeated)
    orch, _, _, _ = _build_orchestrator(llm=llm)
    ctx = UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        recent_conversation=("Usuario: quiero estudiar", f"Rako: {repeated}"),
    )

    result = orch.handle_turn(_input(user_context=ctx))

    assert len(llm.calls) == 2  # original + reintento de reformulación
    assert llm.contexts[0].support_hint is None
    assert llm.contexts[1].support_hint is not None
    assert "Reformula" in llm.contexts[1].support_hint
    assert result.metadata["repeat_retry"] is True


def test_fresh_llm_response_does_not_retry() -> None:
    llm = _FakeLLMClient(response_text="¿Y si partimos anotando las tres dudas del capítulo?")
    orch, _, _, _ = _build_orchestrator(llm=llm)
    ctx = UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        recent_conversation=("Rako: Partamos con un bloque corto de 25 minutos de cálculo.",),
    )

    result = orch.handle_turn(_input(user_context=ctx))

    assert len(llm.calls) == 1
    assert result.metadata["repeat_retry"] is False


def test_llm_failure_returns_curated_fallback_not_crash() -> None:
    orch, _, _, _ = _build_orchestrator(llm=_ExplodingLLMClient())  # type: ignore[arg-type]

    result = orch.handle_turn(_input())

    assert result.kind is TurnKind.LLM_FALLBACK
    assert "repites" in result.text
    assert result.metadata["reason"] == "llm_error"


def test_retriever_failure_degrades_to_llm_without_chunks() -> None:
    orch, _, llm, _ = _build_orchestrator(retriever=_ExplodingRetriever())  # type: ignore[arg-type]

    result = orch.handle_turn(_input())

    assert result.kind is TurnKind.LLM_RESPONSE
    assert result.rag_chunk_ids == ()
    assert len(llm.calls) == 1


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


# ---------------------------------------------------------------------------
# Aftercare post-crisis: los turnos que SIGUEN a una crisis no vuelven al LLM
# ---------------------------------------------------------------------------


def test_post_crisis_followup_stays_in_aftercare_not_llm() -> None:
    from datetime import timedelta

    orch, retriever, llm, journal = _build_orchestrator()

    # El turno siguiente a una crisis, sin repetir palabras clave, no debe
    # caer al LLM ("abre tu libro de cálculo"): presencia + derivación.
    result = orch.handle_turn(
        _input(
            transcript="no quiero contactar a nadie, no se que hacer",
            recent_crisis_at=_now() - timedelta(minutes=2),
        )
    )

    assert result.kind is TurnKind.CRISIS_AFTERCARE
    assert llm.calls == []  # el LLM no se invoca
    assert retriever.queries == []  # ni el RAG
    assert result.notify_contact is False  # ya se alertó en la crisis
    assert result.show_resources is True
    assert journal.entries == []  # el aftercare no re-registra crisis


def test_aftercare_response_derives_and_never_suggests_studying() -> None:
    from datetime import timedelta

    orch, _, _, _ = _build_orchestrator()

    result = orch.handle_turn(
        _input(
            transcript="ayudame con calculo por favor",
            recent_crisis_at=_now() - timedelta(minutes=1),
        )
    )

    assert result.kind is TurnKind.CRISIS_AFTERCARE
    lowered = result.text.lower()
    assert "estudi" not in lowered  # nada de "estudia/estudiar"
    assert "131" in result.text  # deriva a recursos de crisis


def test_fresh_crisis_during_aftercare_still_runs_full_protocol() -> None:
    from datetime import timedelta

    orch, _, llm, journal = _build_orchestrator()

    result = orch.handle_turn(
        _input(
            transcript="quiero morir",
            recent_crisis_at=_now() - timedelta(minutes=2),
        )
    )

    # Una crisis fresca dentro de la ventana debe correr el protocolo
    # completo (alerta al contacto, journal), no el aftercare pasivo.
    assert result.kind is TurnKind.CRISIS_PROTOCOL
    assert result.notify_contact is True
    assert len(journal.entries) == 1
    assert llm.calls == []


def test_aftercare_window_expires_returns_to_normal_llm() -> None:
    from datetime import timedelta

    orch, _, llm, _ = _build_orchestrator()

    result = orch.handle_turn(
        _input(
            transcript="ayudame con una tarea",
            recent_crisis_at=_now() - timedelta(hours=3),
        )
    )

    assert result.kind is TurnKind.LLM_RESPONSE
    assert len(llm.calls) == 1


def test_future_crisis_timestamp_does_not_trigger_aftercare() -> None:
    from datetime import timedelta

    orch, _, llm, _ = _build_orchestrator()

    # Timestamp en el futuro (reloj desincronizado) no debe abrir aftercare.
    result = orch.handle_turn(
        _input(
            transcript="ayudame con una tarea",
            recent_crisis_at=_now() + timedelta(minutes=10),
        )
    )

    assert result.kind is TurnKind.LLM_RESPONSE
    assert len(llm.calls) == 1


def test_no_recent_crisis_means_no_aftercare() -> None:
    orch, _, llm, _ = _build_orchestrator()

    result = orch.handle_turn(_input(transcript="ayudame con una tarea"))

    assert result.kind is TurnKind.LLM_RESPONSE
    assert len(llm.calls) == 1
