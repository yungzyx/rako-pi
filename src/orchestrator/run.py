"""RunLoop — el loop principal reactivo del cerebro.

Reactividad: se suscribe al `HardwareEventBus` y procesa los eventos
en el thread principal (no en el callback que disparó el evento). Esto
mantiene `_handle_event` simple y testeable, y evita race conditions
con el orquestador.

Eventos soportados:
- BUTTON_PANIC / BUTTON_EMERGENCY → turn de crisis (bypass LLM).
- TOUCH                            → voice turn completo
                                     (LISTENING → THINKING → SPEAKING → OFF).
- PIR_MOTION                       → ignorado en el path reactivo;
                                     reservado para el detector proactivo.

El loop también drena `sync` cada N iteraciones para que eventos
encolados no se queden parados cuando hay red.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from hardware.types import HardwareEvent, HardwareEventKind, LEDState
from orchestrator.orchestrator import TurnInput
from orchestrator.types import default_user_context
from safety.types import PanicSource

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunConfig:
    capture_seconds: float = 5.0
    sleep_seconds: float = 0.05
    drain_every_n_iterations: int = 20


def _utc_now() -> datetime:  # pragma: no cover - default factory
    return datetime.now(UTC)


class RunLoop:
    def __init__(
        self,
        *,
        app,  # bootstrap.Application — typed as Any to avoid import cycle
        config: RunConfig | None = None,
        now: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._app = app
        self._config = config or RunConfig()
        self._now = now
        self._sleep = sleep
        self._pending: list[HardwareEvent] = []
        self._iteration = 0
        self._stopped = False
        app.event_bus.subscribe(self._enqueue)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._stopped = True

    def run(self, max_iterations: int | None = None) -> None:
        while not self._stopped:
            if max_iterations is not None and self._iteration >= max_iterations:
                break
            self._tick()
            self._iteration += 1
            self._sleep(self._config.sleep_seconds)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _enqueue(self, event: HardwareEvent) -> None:
        self._pending.append(event)

    def _tick(self) -> None:
        # Snapshot + clear: nuevos eventos durante el tick van al próximo.
        events, self._pending = self._pending, []
        for event in events:
            try:
                self._handle_event(event)
            except Exception:
                _log.exception("error handling event %s", event.kind)

        if self._iteration > 0 and self._iteration % self._config.drain_every_n_iterations == 0:
            try:
                self._app.sync.drain()
            except Exception:
                _log.exception("sync drain failed")

    def _handle_event(self, event: HardwareEvent) -> None:
        if (
            event.kind is HardwareEventKind.BUTTON_PANIC
            or event.kind is HardwareEventKind.BUTTON_EMERGENCY
        ):
            self._handle_panic(PanicSource.PHYSICAL)
        elif event.kind is HardwareEventKind.TOUCH:
            self._handle_voice_turn()
        # PIR_MOTION: reservado al detector proactivo, no dispara turn.

    def _handle_panic(self, source: PanicSource) -> None:
        now = self._now()
        turn = TurnInput(
            transcript="",
            emotion=None,
            panic_button=source,
            emotion_history=(),
            last_high_distress_at=None,
            last_interaction_at=None,
            user_context=default_user_context(now),
            now=now,
        )
        result = self._app.orchestrator.handle_turn(turn)
        self._dispatch(result)

    def _handle_voice_turn(self) -> None:
        self._app.leds.set_state(LEDState.LISTENING)
        try:
            audio = self._app.capture.capture(self._config.capture_seconds)
        except Exception:
            _log.exception("capture failed")
            self._app.leds.turn_off()
            return

        transcript = self._transcribe(audio)
        if not transcript.strip():
            # STT no entendió nada — silencio o ruido. Volver a idle sin
            # quemar tokens del LLM ni armar un turn vacío.
            self._app.leds.turn_off()
            return

        self._app.leds.set_state(LEDState.THINKING)
        now = self._now()
        turn = TurnInput(
            transcript=transcript,
            emotion=None,
            panic_button=None,
            emotion_history=(),
            last_high_distress_at=None,
            last_interaction_at=now,
            user_context=default_user_context(now),
            now=now,
        )
        result = self._app.orchestrator.handle_turn(turn)
        self._dispatch(result)

    def _transcribe(self, audio) -> str:
        stt = getattr(self._app, "stt", None)
        if stt is None:
            return ""
        try:
            return stt.transcribe(audio).text
        except Exception:
            _log.exception("STT failed; treating transcript as empty")
            return ""

    def _dispatch(self, result) -> None:
        self._app.leds.set_state(LEDState.SPEAKING)
        if result.text:
            self._speak(result.text)
        self._app.leds.turn_off()

    def _speak(self, text: str) -> None:
        tts = getattr(self._app, "tts", None)
        if tts is None:
            return
        try:
            synth = tts.synthesize(text)
            self._app.playback.play(synth.audio)
        except Exception:
            _log.exception("TTS or playback failed")
