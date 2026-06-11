"""WhatsApp check-ins and inbound message handling.

This module keeps WhatsApp logic deterministic and testable. It does not call
Meta directly; callers inject a client adapter.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from channels.whatsapp.client import WhatsAppClient, WhatsAppOutboundMessage
from db.database import Database
from db.types import EmotionalStateRecord
from emotion.types import EmotionalVector
from product.user_config import UserConfigService
from productivity.progress import (
    ProgressPeriod,
    build_external_progress_message,
    build_progress_summary,
)
from productivity.runtime import maybe_start_focus_from_transcript
from safety.detector import detect_crisis
from safety.responses import pick_response
from safety.types import CrisisInput, CrisisLevel

_LAST_CHECKIN_KEY = "whatsapp.last_checkin"


@dataclass(frozen=True, slots=True)
class WhatsAppInboundResult:
    action: str
    response_text: str
    crisis: bool = False
    stored_mood: str | None = None
    focus_session_id: str | None = None


class WhatsAppService:
    def __init__(self, db: Database, client: WhatsAppClient) -> None:
        self._db = db
        self._client = client

    def send_checkin(
        self,
        *,
        to: str,
        now: datetime | None = None,
    ) -> WhatsAppOutboundMessage:
        now = _ensure_aware(now or datetime.now(UTC))
        if not UserConfigService(self._db).whatsapp_can_send():
            return self._consent_required(to=to, now=now)
        text = "Hey, soy Rako. Check-in rápido: ¿cómo te sientes ahora: bien, normal o bajo?"
        message = self._client.send_text(
            to=to,
            text=text,
            kind="CHECKIN",
            metadata={"sent_at": now.isoformat()},
        )
        self._db.config.set(
            _LAST_CHECKIN_KEY,
            json.dumps({"to": to, "sent_at": now.isoformat()}, ensure_ascii=False),
        )
        return message

    def send_progress_report(
        self,
        *,
        to: str,
        period: ProgressPeriod = "today",
        now: datetime | None = None,
    ) -> WhatsAppOutboundMessage:
        now = _ensure_aware(now or datetime.now(UTC))
        if not UserConfigService(self._db).progress_reports_can_send():
            return self._consent_required(to=to, now=now)
        summary = build_progress_summary(self._db, now=now, period=period)
        return self._client.send_text(
            to=to,
            text=build_external_progress_message(summary),
            kind="PROGRESS_REPORT",
            metadata={"period": period, "sent_at": now.isoformat()},
        )

    def send_action_menu(
        self,
        *,
        to: str,
        now: datetime | None = None,
    ) -> WhatsAppOutboundMessage:
        now = _ensure_aware(now or datetime.now(UTC))
        if not UserConfigService(self._db).whatsapp_can_send():
            return self._consent_required(to=to, now=now)
        text = (
            "¿Qué hacemos ahora?\n"
            "1. Elegir una tarea corta\n"
            "2. Foco de 25 minutos\n"
            "3. Revisar progreso\n"
            "4. Check-in de ánimo"
        )
        return self._client.send_text(
            to=to,
            text=text,
            kind="ACTION_MENU",
            metadata={"sent_at": now.isoformat()},
        )

    def _consent_required(self, *, to: str, now: datetime) -> WhatsAppOutboundMessage:
        return self._client.send_text(
            to=to,
            text=(
                "Necesito que actives WhatsApp en la configuración de Rako antes de enviarte "
                "avisos o reportes por este canal."
            ),
            kind="CONSENT_REQUIRED",
            metadata={"sent_at": now.isoformat()},
        )

    def handle_inbound(
        self,
        *,
        from_number: str,
        text: str,
        now: datetime | None = None,
    ) -> WhatsAppInboundResult:
        now = _ensure_aware(now or datetime.now(UTC))
        clean_text = " ".join(text.strip().split())
        if not clean_text:
            return self._reply(
                to=from_number,
                action="EMPTY",
                response_text="Te leo. Mándame una frase corta cuando puedas.",
            )

        crisis_signal = detect_crisis(
            CrisisInput(
                transcript=clean_text,
                emotion_history=self._db.emotional_states.list_samples_in_window(
                    end=now,
                    lookback=timedelta(hours=1),
                ),
                panic_button=None,
                last_high_distress_at=None,
                last_interaction_at=None,
                now=now,
            )
        )
        if crisis_signal.level is CrisisLevel.CRISIS:
            response = pick_response(crisis_signal)
            return self._reply(
                to=from_number,
                action="CRISIS",
                response_text=response.text,
                crisis=True,
            )

        mood = _classify_mood(clean_text)
        if mood is not None:
            self._store_mood(mood=mood, now=now)
            return self._reply(
                to=from_number,
                action="MOOD_RECORDED",
                response_text=_mood_response(mood),
                stored_mood=mood,
            )

        menu_result = self._handle_menu_choice(clean_text, from_number=from_number, now=now)
        if menu_result is not None:
            return menu_result

        focus = maybe_start_focus_from_transcript(clean_text, db=self._db, now=now)
        if focus is not None:
            return self._reply(
                to=from_number,
                action="FOCUS",
                response_text=focus.response_text,
                focus_session_id=focus.session.id if focus.session else None,
            )

        return self._reply(
            to=from_number,
            action="GENERAL",
            response_text=(
                "Te leo. Si quieres, dime cómo te sientes o escribe algo como "
                "'quiero estudiar 25 minutos'."
            ),
        )

    def _handle_menu_choice(
        self,
        text: str,
        *,
        from_number: str,
        now: datetime,
    ) -> WhatsAppInboundResult | None:
        normalized = text.strip().lower()
        if normalized in {"1", "tarea", "tarea corta"}:
            next_task = self._db.tasks.list_pending()
            response = (
                "Partamos chico: abre tu siguiente tarea pendiente y haz solo el primer paso durante 10 minutos."
                if next_task
                else "No veo tareas pendientes. Dime una tarea y la convertimos en un primer paso de 10 minutos."
            )
            return self._reply(to=from_number, action="MENU_TASK", response_text=response)
        if normalized in {"2", "foco", "pomodoro"}:
            return self._reply(
                to=from_number,
                action="MENU_FOCUS",
                response_text="Dime la actividad y duración, por ejemplo: estudiar cálculo 25 minutos.",
            )
        if normalized in {"3", "progreso", "avance"}:
            summary = build_progress_summary(self._db, now=now, period="today")
            return self._reply(
                to=from_number,
                action="MENU_PROGRESS",
                response_text=build_external_progress_message(summary),
            )
        if normalized in {"4", "ánimo", "animo", "mood"}:
            return self._reply(
                to=from_number,
                action="MENU_MOOD",
                response_text="Dime rápido cómo estás: bien, normal o bajo.",
            )
        return None

    def _reply(
        self,
        *,
        to: str,
        action: str,
        response_text: str,
        crisis: bool = False,
        stored_mood: str | None = None,
        focus_session_id: str | None = None,
    ) -> WhatsAppInboundResult:
        metadata = {"action": action}
        if focus_session_id:
            metadata["focus_session_id"] = focus_session_id
        self._client.send_text(to=to, text=response_text, kind=action, metadata=metadata)
        return WhatsAppInboundResult(
            action=action,
            response_text=response_text,
            crisis=crisis,
            stored_mood=stored_mood,
            focus_session_id=focus_session_id,
        )

    def _store_mood(self, *, mood: str, now: datetime) -> None:
        vector = _mood_vector(mood)
        self._db.emotional_states.append(
            EmotionalStateRecord(
                id=f"wa_{uuid4().hex}",
                at=now,
                vector=vector,
                trigger_event="whatsapp_checkin",
                confidence=0.7,
            )
        )


def inbound_result_to_dict(result: WhatsAppInboundResult) -> dict[str, object]:
    return asdict(result)


def outbound_message_to_dict(message: WhatsAppOutboundMessage) -> dict[str, object]:
    return asdict(message)


def _classify_mood(text: str) -> str | None:
    lowered = text.lower()
    if any(word in lowered for word in ("mal", "bajo", "baja", "triste", "agotado", "agotada")):
        return "low"
    if any(
        word in lowered
        for word in ("normal", "neutro", "ok", "ahi", "ahí", "mas o menos", "más o menos")
    ):
        return "neutral"
    if any(word in lowered for word in ("bien", "motivado", "motivada", "tranquilo", "tranquila")):
        return "good"
    return None


def _mood_vector(mood: str) -> EmotionalVector:
    if mood == "low":
        return EmotionalVector(valence=-0.55, arousal=0.55, dominance=0.35)
    if mood == "good":
        return EmotionalVector(valence=0.55, arousal=0.35, dominance=0.65)
    return EmotionalVector(valence=0.0, arousal=0.3, dominance=0.5)


def _mood_response(mood: str) -> str:
    if mood == "low":
        return "Gracias por decirme. Bajemos la exigencia: ¿te sirve partir con 10 minutos suaves?"
    if mood == "good":
        return "Bien. Aprovechemos esa energía con un bloque corto y claro cuando quieras."
    return "Gracias. Podemos ir paso a paso; dime si quieres estudiar, descansar o planear."


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
