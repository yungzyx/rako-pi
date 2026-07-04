"""RunLoop — el loop principal reactivo del cerebro.

Reactividad: se suscribe al `HardwareEventBus` y procesa los eventos
en el thread principal (no en el callback que disparó el evento). Esto
mantiene `_handle_event` simple y testeable, y evita race conditions
con el orquestador.

Eventos soportados:
- BUTTON_PANIC / BUTTON_EMERGENCY → turn de crisis (bypass LLM).
- TOUCH / WAKE_WORD                → voice turn completo
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
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from db.types import Interaction, InteractionType
from hardware.types import HardwareEvent, HardwareEventKind, LEDState
from orchestrator.context import build_user_context, count_recent_low_mood_days
from orchestrator.memory import ConversationMemory
from orchestrator.orchestrator import TurnInput, TurnResult
from orchestrator.voice_commands import parse_remember_command
from product.user_config import UserConfigService
from safety.types import PanicSource

_log = logging.getLogger(__name__)

# Al reiniciar, retomamos la conversación solo si es realmente reciente —
# una charla de ayer no debe tratarse como "conversación en curso".
_MEMORY_RESTORE_WINDOW = timedelta(minutes=45)


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
        self._memory = ConversationMemory()
        self._restore_recent_memory()
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
        elif event.kind is HardwareEventKind.TOUCH or event.kind is HardwareEventKind.WAKE_WORD:
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
            user_context=build_user_context(self._app.db, now),
            now=now,
        )
        result = self._app.orchestrator.handle_turn(turn)
        self._dispatch(result)

    def _restore_recent_memory(self) -> None:
        """Retoma la conversación si el proceso se reinició a mitad de sesión.

        Solo interacciones dentro de la ventana reciente; en modo privado no
        hay historial persistido y tampoco lo leemos.
        """
        if self._app.settings.rako_mode == "private":
            return
        cutoff = self._now() - _MEMORY_RESTORE_WINDOW
        recent = [
            interaction
            for interaction in self._app.db.interactions.list_recent(limit=self._memory.max_turns)
            if _as_aware(interaction.timestamp) >= cutoff
        ]
        for interaction in reversed(recent):  # list_recent viene nuevo→viejo
            self._memory.add_turn(
                user=interaction.transcription_excerpt or "",
                rako=interaction.response_text or "",
            )

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

        if self._handle_remember_command(transcript):
            return

        self._app.leds.set_state(LEDState.THINKING)
        now = self._now()
        channels = UserConfigService(self._app.db).get_channels()
        turn = TurnInput(
            transcript=transcript,
            emotion=None,
            panic_button=None,
            emotion_history=(),
            last_high_distress_at=None,
            last_interaction_at=now,
            user_context=build_user_context(
                self._app.db,
                now,
                recent_conversation=self._memory.lines(),
            ),
            now=now,
            recent_low_mood_days=count_recent_low_mood_days(self._app.db, now),
            wellbeing_unit_name=channels.wellbeing_unit_name,
            wellbeing_unit_phone=channels.wellbeing_unit_phone,
        )
        result = self._app.orchestrator.handle_turn(turn)
        self._memory.add_turn(user=transcript, rako=result.text)
        self._record_interaction(transcript=transcript, result=result, now=now)
        self._dispatch(result)

    def _handle_remember_command(self, transcript: str) -> bool:
        """Comando local "recuerda que ..." — guarda preferencia sin LLM."""
        memory_text = parse_remember_command(transcript)
        if memory_text is None:
            return False
        now = self._now()
        try:
            memory = UserConfigService(self._app.db).add_memory(
                text=memory_text, category="preference", now=now
            )
        except ValueError:
            _log.warning("remember command rejected by memory validation")
            return False
        confirmation = f"Listo, lo voy a recordar: {memory.text}"
        self._app.leds.set_state(LEDState.SPEAKING)
        self._speak(confirmation)
        self._app.leds.turn_off()
        self._memory.add_turn(user=transcript, rako=confirmation)
        return True

    def _record_interaction(self, *, transcript: str, result: TurnResult, now: datetime) -> None:
        # "Modo no-grabación" (CLAUDE.md §4.1.4): con rako_mode=private el
        # robot sigue operando pero no persiste historial de interacciones.
        if self._app.settings.rako_mode == "private":
            return
        self._app.db.interactions.append(
            Interaction(
                id=f"turn_{uuid4().hex}",
                timestamp=now,
                type=InteractionType.USER_VOICE,
                transcription_excerpt=transcript,
                emotion=None,
                response_id=None,
                response_text=result.text,
            )
        )

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


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
