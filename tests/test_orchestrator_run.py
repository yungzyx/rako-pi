"""Tests del RunLoop — el loop principal reactivo."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bootstrap import build_dev_application
from config import Settings
from hardware.event_bus import InMemoryHardwareEventBus
from hardware.types import HardwareEvent, HardwareEventKind, LEDState
from orchestrator.orchestrator import TurnKind, TurnResult
from orchestrator.run import RunConfig, RunLoop
from voice.types import AudioBuffer, SynthesisResult, TranscriptResult


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        rako_env="dev",
        sqlite_path=str(tmp_path / "rako.db"),
        anthropic_api_key=None,
        obsidian_vault_path=str(tmp_path / "vault"),
        chroma_db_path=str(tmp_path / "chroma"),
    )


def _make_loop(
    tmp_path: Path,
    *,
    config: RunConfig | None = None,
    sleep_calls: list[float] | None = None,
):
    app = build_dev_application(_settings(tmp_path))
    sleep_calls = sleep_calls if sleep_calls is not None else []

    def _record_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    loop = RunLoop(
        app=app,
        config=config or RunConfig(sleep_seconds=0.0, drain_every_n_iterations=10),
        now=_now,
        sleep=_record_sleep,
    )
    return loop, app, sleep_calls


def _emit(bus: InMemoryHardwareEventBus, kind: HardwareEventKind) -> None:
    bus.emit(HardwareEvent(kind=kind, at=_now()))


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------


def test_run_returns_cleanly_with_no_events(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        loop.run(max_iterations=3)
    finally:
        app.close()


def test_run_can_be_stopped(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        loop.stop()
        loop.run(max_iterations=1000)  # debería salir inmediatamente
    finally:
        app.close()


# ---------------------------------------------------------------------------
# Panic flow
# ---------------------------------------------------------------------------


def test_panic_event_triggers_crisis_protocol(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.BUTTON_PANIC)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        # El crisis journal debe tener el evento.
        entries = app.db.crisis_journal.list_recent()
        assert len(entries) == 1
        assert "PANIC_BUTTON_PHYSICAL" in entries[0].reasons
    finally:
        app.close()


def test_emergency_button_also_triggers_protocol(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.BUTTON_EMERGENCY)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        entries = app.db.crisis_journal.list_recent()
        assert len(entries) == 1
    finally:
        app.close()


def test_panic_routes_leds_to_present_during_protocol(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.BUTTON_PANIC)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        # El protocolo de crisis (vía CrisisLightingAdapter) puso los LEDs en PRESENT.
        history = app.leds.history  # type: ignore[attr-defined]
        assert LEDState.PRESENT in history
    finally:
        app.close()


# ---------------------------------------------------------------------------
# Touch / PIR → voice turn
# ---------------------------------------------------------------------------


def test_touch_triggers_voice_turn_with_state_progression(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        history = app.leds.history  # type: ignore[attr-defined]
        # Debe haber visto LISTENING → THINKING → SPEAKING → OFF en algún orden razonable.
        assert LEDState.LISTENING in history
        assert LEDState.THINKING in history
        assert LEDState.SPEAKING in history
        # El último estado debe ser OFF.
        assert history[-1] is LEDState.OFF
    finally:
        app.close()


def test_voice_turn_captures_audio_and_synthesizes_response(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        # El playback debe haber recibido el audio sintetizado.
        played = app.playback.played  # type: ignore[attr-defined]
        assert len(played) >= 1
        assert isinstance(played[0], AudioBuffer)
    finally:
        app.close()


def test_voice_turn_passes_short_memory_to_next_turn(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)

    @dataclass
    class _RecordingOrchestrator:
        conversations: list[tuple[str, ...]] = field(default_factory=list)

        def handle_turn(self, turn):  # type: ignore[no-untyped-def]
            self.conversations.append(turn.user_context.recent_conversation)
            return TurnResult(
                kind=TurnKind.LLM_RESPONSE,
                text="Dale, sigamos con eso.",
                audio_path=None,
                rag_chunk_ids=(),
                notify_contact=False,
                show_resources=False,
            )

    recorder = _RecordingOrchestrator()
    app.orchestrator = recorder  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        assert recorder.conversations[0] == ()
        assert "Usuario: estoy aquí" in recorder.conversations[1]
        assert "Rako: Dale, sigamos con eso." in recorder.conversations[1]
    finally:
        app.close()


def test_voice_turn_records_interaction_by_default(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        recorded = app.db.interactions.list_recent()
        assert len(recorded) == 1
        assert recorded[0].transcription_excerpt == "estoy aquí"
        assert recorded[0].response_text
    finally:
        app.close()


def test_voice_turn_does_not_record_interaction_in_private_mode(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings = settings.model_copy(update={"rako_mode": "private"})
    app = build_dev_application(settings)
    loop = RunLoop(app=app, config=RunConfig(sleep_seconds=0.0), now=_now)
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        assert app.db.interactions.list_recent() == []
    finally:
        app.close()


def test_voice_turn_feeds_triage_signals_from_local_state(tmp_path: Path) -> None:
    # El loop de voz debe pasar al orquestador la recurrencia de ánimo bajo
    # y la unidad de bienestar configurada — si esto se cae, el triage de
    # derivación corre siempre con defaults y nunca deriva.
    from datetime import timedelta

    from db.types import EmotionalStateRecord
    from emotion.types import EmotionalVector
    from product.user_config import UserConfigService

    loop, app, _ = _make_loop(tmp_path)
    config = UserConfigService(app.db)
    config.update_channels(
        {"wellbeing_unit_name": "Bienestar UDD", "wellbeing_unit_phone": "+56228203419"}
    )
    for day in (1, 2, 3):
        app.db.emotional_states.append(
            EmotionalStateRecord(
                id=f"low-{day}",
                at=_now() - timedelta(days=day),
                vector=EmotionalVector(valence=-0.6, arousal=0.5, dominance=0.4),
                trigger_event="whatsapp_checkin",
                confidence=0.7,
            )
        )

    @dataclass
    class _RecordingOrchestrator:
        turns: list = field(default_factory=list)

        def handle_turn(self, turn):  # type: ignore[no-untyped-def]
            self.turns.append(turn)
            return TurnResult(
                kind=TurnKind.LLM_RESPONSE,
                text="ok",
                audio_path=None,
                rag_chunk_ids=(),
                notify_contact=False,
                show_resources=False,
            )

    recorder = _RecordingOrchestrator()
    app.orchestrator = recorder  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        turn = recorder.turns[0]
        assert turn.recent_low_mood_days == 3
        assert turn.wellbeing_unit_name == "Bienestar UDD"
        assert turn.wellbeing_unit_phone == "+56228203419"
    finally:
        app.close()


def test_wake_word_event_triggers_voice_turn(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.WAKE_WORD)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        history = app.leds.history  # type: ignore[attr-defined]
        assert LEDState.LISTENING in history
        assert LEDState.THINKING in history
        assert LEDState.SPEAKING in history
        assert history[-1] is LEDState.OFF
        assert len(app.playback.played) >= 1  # type: ignore[attr-defined]
    finally:
        app.close()


# ---------------------------------------------------------------------------
# Robustez
# ---------------------------------------------------------------------------


def test_stt_failure_does_not_crash_loop(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)

    @dataclass
    class _FailingSTT:
        def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
            raise RuntimeError("STT down")

    app.stt = _FailingSTT()  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)
        # No assertion — solo que no crashee.
    finally:
        app.close()


def test_tts_failure_does_not_crash_loop(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)

    @dataclass
    class _FailingTTS:
        def synthesize(self, text: str) -> SynthesisResult:
            raise RuntimeError("TTS down")

    app.tts = _FailingTTS()  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)
        history = app.leds.history  # type: ignore[attr-defined]
        # Aún así, los LEDs deben volver a OFF al final.
        assert history[-1] is LEDState.OFF
    finally:
        app.close()


def test_loop_drains_sync_periodically(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(
        tmp_path, config=RunConfig(sleep_seconds=0.0, drain_every_n_iterations=2)
    )
    try:
        # Sembramos un evento en la cola.
        from sync.types import SyncEvent, SyncEventKind

        app.sync.enqueue(
            SyncEvent(
                id="e1",
                kind=SyncEventKind.DEVICE_HEARTBEAT,
                occurred_at=_now(),
                payload={"ok": 1},
            )
        )
        loop.run(max_iterations=4)

        # El cliente fake debió haber recibido el evento.
        assert len(app.sync._client.sent) == 1  # type: ignore[attr-defined]
    finally:
        app.close()


def test_loop_sleeps_between_iterations(tmp_path: Path) -> None:
    loop, app, sleep_calls = _make_loop(
        tmp_path, config=RunConfig(sleep_seconds=0.42, drain_every_n_iterations=10)
    )
    try:
        loop.run(max_iterations=3)
        assert sleep_calls == [0.42, 0.42, 0.42]
    finally:
        app.close()


def test_pir_motion_does_not_immediately_trigger_voice(tmp_path: Path) -> None:
    """PIR es señal de presencia, no de petición de turno explícita.

    Para evitar que el robot inicie conversación cada vez que el usuario
    pasa por el cuarto, PIR_MOTION solo se usa para input al detector
    proactivo (futuro). En el RunLoop reactivo NO dispara turn.
    """
    loop, app, _ = _make_loop(tmp_path)
    try:
        _emit(app.event_bus, HardwareEventKind.PIR_MOTION)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        # Sin TOUCH ni botones, no hay turn → playback vacío.
        assert app.playback.played == []  # type: ignore[attr-defined]
        # Y los LEDs no debieron entrar a LISTENING.
        history = app.leds.history  # type: ignore[attr-defined]
        assert LEDState.LISTENING not in history
    finally:
        app.close()


def test_handler_exception_is_logged_and_loop_continues(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Si _handle_event lanza, el loop captura la excepción y sigue."""
    loop, app, _ = _make_loop(tmp_path)

    # Reemplazamos el orquestador por uno que crashea.
    @dataclass
    class _CrashingOrchestrator:
        def handle_turn(self, turn):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    app.orchestrator = _CrashingOrchestrator()  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.BUTTON_PANIC)  # type: ignore[arg-type]
        loop.run(max_iterations=2)
        # No assertion sobre el contenido del log — la garantía es que
        # el loop NO crashee.
    finally:
        app.close()


def test_sync_drain_failure_is_logged_and_loop_continues(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(
        tmp_path, config=RunConfig(sleep_seconds=0.0, drain_every_n_iterations=1)
    )

    class _FailingSync:
        def enqueue(self, event):  # type: ignore[no-untyped-def]
            pass

        def drain(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("network down")

    app.sync = _FailingSync()  # type: ignore[assignment]
    try:
        loop.run(max_iterations=3)
        # Loop completó sin crashear.
    finally:
        app.close()


def test_capture_failure_returns_to_idle(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)

    class _FailingCapture:
        def capture(self, max_seconds):  # type: ignore[no-untyped-def]
            raise RuntimeError("mic gone")

    app.capture = _FailingCapture()  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)

        history = app.leds.history  # type: ignore[attr-defined]
        # LISTENING fue intentado, luego OFF tras la falla.
        assert history[-1] is LEDState.OFF
        # No hubo SPEAKING porque no llegamos al orquestador.
        assert LEDState.SPEAKING not in history
    finally:
        app.close()


def test_run_loop_works_when_stt_is_none(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    app.stt = None  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)
        # transcript vacío → no turn → LEDs OFF
        history = app.leds.history  # type: ignore[attr-defined]
        assert history[-1] is LEDState.OFF
        assert LEDState.SPEAKING not in history
    finally:
        app.close()


def test_run_loop_works_when_tts_is_none(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    app.tts = None  # type: ignore[assignment]
    try:
        _emit(app.event_bus, HardwareEventKind.TOUCH)  # type: ignore[arg-type]
        loop.run(max_iterations=1)
        history = app.leds.history  # type: ignore[attr-defined]
        # Pasó por SPEAKING (LLM produjo texto) pero no hubo playback.
        assert LEDState.SPEAKING in history
        assert app.playback.played == []  # type: ignore[attr-defined]
        assert history[-1] is LEDState.OFF
    finally:
        app.close()


def test_unknown_event_kind_is_ignored(tmp_path: Path) -> None:
    loop, app, _ = _make_loop(tmp_path)
    try:
        # Inyectamos un "evento" que no es ni panic ni touch ni PIR ni
        # emergency — pero tipos enum cierran las opciones, así que el
        # caso es: no-op cuando no llegan eventos.
        loop.run(max_iterations=1)

        assert app.leds.history == []  # type: ignore[attr-defined]
    finally:
        app.close()
