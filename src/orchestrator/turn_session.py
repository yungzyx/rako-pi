"""TurnSession — pipeline de turno compartido entre los loops de voz.

Tanto `RunLoop` (orchestrator/run.py) como el loop del botón físico
(scripts/button_conversation.py) necesitan lo mismo alrededor de cada
turno: memoria conversacional con restauración post-reinicio, el comando
local "recuerda que ...", los inputs de triage (días de ánimo bajo,
unidad de bienestar configurada) y la persistencia de interacciones con
el gate de privacidad `rako_mode=private`. Antes cada loop lo cableaba
por su cuenta y divergían: el dispositivo físico no recibía triage ni
persistía historial. Este módulo es la única implementación.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from db.types import Interaction, InteractionType
from orchestrator.context import (
    build_user_context,
    count_recent_low_mood_days,
    find_last_high_distress_at,
    find_last_interaction_at,
)
from orchestrator.memory import ConversationMemory
from orchestrator.orchestrator import TurnInput, TurnKind, TurnResult
from orchestrator.preferences import extract_preference
from orchestrator.voice_commands import parse_remember_command
from product.user_config import UserConfigService
from safety.detector import detect_crisis
from safety.types import CrisisInput

_log = logging.getLogger(__name__)

# Al reiniciar, retomamos la conversación solo si es realmente reciente —
# una charla de ayer no debe tratarse como "conversación en curso".
MEMORY_RESTORE_WINDOW = timedelta(minutes=45)

# Sugerencia de memoria pendiente de confirmación por voz (opt-in).
_PENDING_MEMORY_KEY = "voice.pending_memory"
_PENDING_MEMORY_TTL = timedelta(minutes=15)
_CONFIRM_MEMORY_PHRASES = frozenset(
    {
        "si recuerdalo",
        "sí recuérdalo",
        "si, recuerdalo",
        "sí, recuérdalo",
        "recuerdalo",
        "recuérdalo",
        "guardalo",
        "guárdalo",
        "si guardalo",
        "sí guárdalo",
        "dale recuerdalo",
        "dale recuérdalo",
    }
)
_DECLINE_MEMORY_PHRASES = frozenset({"no", "no gracias", "no, gracias", "mejor no"})


def _utc_now() -> datetime:  # pragma: no cover - default factory
    return datetime.now(UTC)


class TurnSession:
    """Estado conversacional de un dispositivo entre turnos de voz."""

    def __init__(
        self,
        *,
        db,  # db.database.Database — Any para no acoplar el import
        settings,  # config.Settings
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._db = db
        self._settings = settings
        self._now = now
        self.memory = ConversationMemory()

    # ------------------------------------------------------------------
    # Memoria conversacional
    # ------------------------------------------------------------------

    def restore_recent_memory(self) -> None:
        """Retoma la conversación si el proceso se reinició a mitad de sesión.

        Solo interacciones dentro de la ventana reciente; en modo privado no
        hay historial persistido y tampoco lo leemos.
        """
        if self._settings.rako_mode == "private":
            return
        cutoff = self._now() - MEMORY_RESTORE_WINDOW
        recent = [
            interaction
            for interaction in self._db.interactions.list_recent(limit=self.memory.max_turns)
            if _as_aware(interaction.timestamp) >= cutoff
        ]
        for interaction in reversed(recent):  # list_recent viene nuevo→viejo
            self.memory.add_turn(
                user=interaction.transcription_excerpt or "",
                rako=interaction.response_text or "",
            )

    def add_exchange(self, *, user: str, rako: str) -> None:
        """Agrega un intercambio solo a la memoria (sin persistir) — para
        turnos locales como música o foco que no pasan por el orquestador."""
        self.memory.add_turn(user=user, rako=rako)

    # ------------------------------------------------------------------
    # Comando local "recuerda que ..."
    # ------------------------------------------------------------------

    def try_remember_command(self, transcript: str) -> str | None:
        """Guarda una preferencia dictada por voz, sin LLM.

        Devuelve el texto de confirmación (ya agregado a la memoria
        conversacional) o None si el transcript no es un comando de memoria.

        El detector de crisis corre PRIMERO: una frase de crisis dentro de
        un comando de memoria ("recuerda que ya no quiero vivir") debe
        seguir el pipeline normal hacia el protocolo curado, no guardarse
        en silencio como preferencia.
        """
        pending_reply = self._resolve_pending_memory(transcript)
        if pending_reply is not None:
            return pending_reply
        memory_text = parse_remember_command(transcript)
        if memory_text is None:
            return None
        now = self._now()
        signal = detect_crisis(
            CrisisInput(
                transcript=transcript,
                emotion_history=(),
                panic_button=None,
                last_high_distress_at=None,
                last_interaction_at=None,
                now=now,
            )
        )
        if signal.should_bypass_llm:
            return None
        try:
            memory = UserConfigService(self._db).add_memory(
                text=memory_text, category="preference", now=now
            )
        except ValueError:
            _log.warning("remember command rejected by memory validation")
            return None
        confirmation = f"Listo, lo voy a recordar: {memory.text}"
        self.memory.add_turn(user=transcript, rako=confirmation)
        return confirmation

    # ------------------------------------------------------------------
    # Aprendizaje opt-in de preferencias (nunca silencioso)
    # ------------------------------------------------------------------

    def suggest_preference(self, transcript: str, result: TurnResult) -> str | None:
        """Si el turno normal mencionó una preferencia de estudio, deja una
        sugerencia pendiente y devuelve la pregunta para que el loop la
        hable DESPUÉS de la respuesta principal. Solo turnos LLM_RESPONSE
        (nunca crisis/derivaciones) y solo si no existe una memoria
        similar."""
        if result.kind is not TurnKind.LLM_RESPONSE:
            return None
        candidate = extract_preference(transcript)
        if candidate is None:
            return None
        candidate_lower = candidate.lower()
        for memory in UserConfigService(self._db).list_memory():
            existing = memory.text.lower()
            if candidate_lower in existing or existing in candidate_lower:
                return None
        now = self._now()
        self._db.config.set(
            _PENDING_MEMORY_KEY,
            json.dumps(
                {
                    "text": candidate,
                    "expires_at": (now + _PENDING_MEMORY_TTL).isoformat(),
                },
                ensure_ascii=False,
            ),
        )
        return f"Oye, ¿quieres que recuerde esto: {candidate}? Dime: sí, recuérdalo."

    def _resolve_pending_memory(self, transcript: str) -> str | None:
        pending = self._read_pending_memory()
        if pending is None:
            return None
        normalized = " ".join(transcript.strip().split()).lower().strip(".!?¡¿ ")
        if normalized in _CONFIRM_MEMORY_PHRASES:
            self._db.config.delete(_PENDING_MEMORY_KEY)
            try:
                memory = UserConfigService(self._db).add_memory(
                    text=pending, category="preference", now=self._now()
                )
            except ValueError:
                _log.warning("pending memory rejected by validation")
                return None
            confirmation = f"Listo, lo voy a recordar: {memory.text}"
            self.memory.add_turn(user=transcript, rako=confirmation)
            return confirmation
        if normalized in _DECLINE_MEMORY_PHRASES:
            self._db.config.delete(_PENDING_MEMORY_KEY)
            reply = "Perfecto, no lo guardo. Sigamos."
            self.memory.add_turn(user=transcript, rako=reply)
            return reply
        return None

    def _read_pending_memory(self) -> str | None:
        raw = self._db.config.get(_PENDING_MEMORY_KEY)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._db.config.delete(_PENDING_MEMORY_KEY)
            return None
        if not isinstance(payload, dict):
            self._db.config.delete(_PENDING_MEMORY_KEY)
            return None
        expires_at = payload.get("expires_at")
        if isinstance(expires_at, str) and datetime.fromisoformat(expires_at) <= self._now():
            self._db.config.delete(_PENDING_MEMORY_KEY)
            return None
        text = payload.get("text")
        return text if isinstance(text, str) and text.strip() else None

    # ------------------------------------------------------------------
    # Turno completo vía orquestador
    # ------------------------------------------------------------------

    def build_turn_input(self, transcript: str, *, now: datetime | None = None) -> TurnInput:
        """TurnInput con todo lo que el orquestador necesita para triage y
        detección: contexto con conversación reciente, días de ánimo bajo,
        unidad de bienestar, y las señales vivas del trigger de
        inactividad post-angustia (última angustia alta registrada +
        última interacción persistida — None en modo privado, donde ese
        trigger queda apagado)."""
        now = now or self._now()
        channels = UserConfigService(self._db).get_channels()
        return TurnInput(
            transcript=transcript,
            emotion=None,
            panic_button=None,
            emotion_history=(),
            last_high_distress_at=find_last_high_distress_at(self._db, now),
            last_interaction_at=find_last_interaction_at(self._db),
            user_context=build_user_context(
                self._db,
                now,
                recent_conversation=self.memory.lines(),
            ),
            now=now,
            recent_low_mood_days=count_recent_low_mood_days(self._db, now),
            wellbeing_unit_name=channels.wellbeing_unit_name,
            wellbeing_unit_phone=channels.wellbeing_unit_phone,
        )

    def complete_turn(self, *, transcript: str, result: TurnResult, now: datetime) -> None:
        """Cierra el turno: memoria conversacional + persistencia local."""
        self.memory.add_turn(user=transcript, rako=result.text)
        self._record_interaction(transcript=transcript, result=result, now=now)

    def _record_interaction(self, *, transcript: str, result: TurnResult, now: datetime) -> None:
        # "Modo no-grabación" (CLAUDE.md §4.1.4): con rako_mode=private el
        # robot sigue operando pero no persiste historial de interacciones.
        if self._settings.rako_mode == "private":
            return
        self._db.interactions.append(
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


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
