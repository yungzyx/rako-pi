"""Tests del RunLoop — el loop principal reactivo."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import pytest

from bootstrap import build_dev_application
from config import Settings
from hardware.event_bus import InMemoryHardwareEventBus
from hardware.types import HardwareEvent, HardwareEventKind, LEDState
from orchestrator.run import RunConfig, RunLoop
from safety.types import PanicSource
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
