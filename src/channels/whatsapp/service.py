"""WhatsApp check-ins and inbound message handling.

This module keeps WhatsApp logic deterministic and testable. It does not call
Meta directly; callers inject a client adapter.

El servicio es el orquestador del canal: envíos salientes con gates de
consentimiento, y el pipeline de entrada (crisis PRIMERO, luego
autenticación de remitente, luego los handlers por dominio en
`pending_flows` / `memory_commands` / `config_commands` / `menu` / `mood`).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from channels.whatsapp.client import WhatsAppClient, WhatsAppOutboundMessage
from channels.whatsapp.config_commands import handle_config_command
from channels.whatsapp.memory_commands import handle_memory_command
from channels.whatsapp.menu import MENU_TEXT, handle_menu_choice
from channels.whatsapp.mood import classify_mood, mood_response, store_mood
from channels.whatsapp.pending_flows import handle_pending, pending_key
from channels.whatsapp.results import (
    WhatsAppInboundResult,
    ensure_aware,
    inbound_result_to_dict,
    outbound_message_to_dict,
)
from db.database import Database
from orchestrator.context import count_recent_low_mood_days
from product.user_config import UserConfigService
from productivity.coaching import build_coaching_recommendation
from productivity.progress import (
    ProgressPeriod,
    build_external_progress_message,
    build_progress_summary,
)
from productivity.runtime import maybe_start_focus_from_transcript
from safety.detector import detect_crisis
from safety.responses import pick_response
from safety.scope import build_scope_redirect_response, build_wellbeing_referral_response
from safety.triage import TriageLevel, triage_turn
from safety.types import CrisisInput, CrisisLevel

__all__ = [
    "WhatsAppInboundResult",
    "WhatsAppService",
    "inbound_result_to_dict",
    "outbound_message_to_dict",
]

_log = logging.getLogger(__name__)

_LAST_CHECKIN_KEY = "whatsapp.last_checkin"


class WhatsAppService:
    def __init__(self, db: Database, client: WhatsAppClient) -> None:
        self._db = db
        self._client = client

    # ------------------------------------------------------------------
    # Salientes (con gates de consentimiento)
    # ------------------------------------------------------------------

    def send_checkin(
        self,
        *,
        to: str,
        now: datetime | None = None,
    ) -> WhatsAppOutboundMessage:
        now = ensure_aware(now or datetime.now(UTC))
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
        now = ensure_aware(now or datetime.now(UTC))
        if not UserConfigService(self._db).progress_reports_can_send():
            return self._consent_required(to=to, now=now)
        summary = build_progress_summary(self._db, now=now, period=period)
        return self._client.send_text(
            to=to,
            text=build_external_progress_message(summary),
            kind="PROGRESS_REPORT",
            metadata={"period": period, "sent_at": now.isoformat()},
        )

    def send_smart_checkin(
        self,
        *,
        to: str,
        now: datetime | None = None,
    ) -> WhatsAppOutboundMessage:
        now = ensure_aware(now or datetime.now(UTC))
        config = UserConfigService(self._db)
        if not config.proactive_messages_can_send():
            return self._consent_required(to=to, now=now)
        recommendation = build_coaching_recommendation(
            self._db,
            now=now,
            include_progress=config.progress_reports_can_send(),
        )
        message = self._client.send_text(
            to=to,
            text=recommendation.text,
            kind="SMART_CHECKIN",
            metadata={
                "sent_at": now.isoformat(),
                "recommendation": recommendation.kind,
                **recommendation.metadata,
            },
        )
        self._db.config.set(
            _LAST_CHECKIN_KEY,
            json.dumps(
                {
                    "to": to,
                    "sent_at": now.isoformat(),
                    "kind": recommendation.kind,
                },
                ensure_ascii=False,
            ),
        )
        return message

    def send_action_menu(
        self,
        *,
        to: str,
        now: datetime | None = None,
    ) -> WhatsAppOutboundMessage:
        now = ensure_aware(now or datetime.now(UTC))
        if not UserConfigService(self._db).whatsapp_can_send():
            return self._consent_required(to=to, now=now)
        return self._client.send_text(
            to=to,
            text=MENU_TEXT,
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

    # ------------------------------------------------------------------
    # Entrantes — crisis primero, luego autenticación, luego handlers
    # ------------------------------------------------------------------

    def handle_inbound(
        self,
        *,
        from_number: str,
        text: str,
        now: datetime | None = None,
    ) -> WhatsAppInboundResult:
        now = ensure_aware(now or datetime.now(UTC))
        clean_text = " ".join(text.strip().split())
        if not clean_text:
            return self._reply(
                to=from_number,
                action="EMPTY",
                response_text="Te leo. Mándame una frase corta cuando puedas.",
            )

        crisis_result = self._crisis_result(clean_text, from_number=from_number, now=now)
        if crisis_result is not None:
            return crisis_result

        if not self._is_authorized_sender(from_number):
            _log.warning(
                "whatsapp inbound from unpaired number ending in %s — ignoring",
                from_number[-4:],
            )
            return self._reply(
                to=from_number,
                action="UNAUTHORIZED",
                response_text="No reconozco este número. Escríbeme desde el número configurado en Rako.",
            )

        return self._dispatch_authorized(clean_text, from_number=from_number, now=now)

    def _crisis_result(
        self, clean_text: str, *, from_number: str, now: datetime
    ) -> WhatsAppInboundResult | None:
        """El veto de crisis corre ANTES que cualquier otra rama — incluso
        para números no emparejados (la respuesta curada no expone datos)."""
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
        if crisis_signal.level is not CrisisLevel.CRISIS:
            return None
        self._clear_pending(from_number)
        response = pick_response(crisis_signal)
        self._db.crisis_journal.record(crisis_signal, response_id=response.id)
        return self._reply(
            to=from_number,
            action="CRISIS",
            response_text=response.text,
            crisis=True,
        )

    def _dispatch_authorized(
        self, clean_text: str, *, from_number: str, now: datetime
    ) -> WhatsAppInboundResult:
        pending_result = handle_pending(self, clean_text, from_number=from_number, now=now)
        if pending_result is not None:
            return pending_result

        memory_result = handle_memory_command(self, clean_text, from_number=from_number)
        if memory_result is not None:
            return memory_result

        config_result = handle_config_command(self, clean_text, from_number=from_number, now=now)
        if config_result is not None:
            return config_result

        # Triage graduado (mismo de la voz, safety/triage.py) ANTES del
        # clasificador de ánimo: "ando triste, necesito un psicólogo" debe
        # derivar a bienestar, no quedar registrado solo como mood.
        triage_result = self._triage_result(clean_text, from_number=from_number, now=now)
        if triage_result is not None:
            return triage_result

        mood = classify_mood(clean_text)
        if mood is not None:
            store_mood(self._db, mood=mood, now=now)
            return self._reply(
                to=from_number,
                action="MOOD_RECORDED",
                response_text=mood_response(mood),
                stored_mood=mood,
            )

        menu_result = handle_menu_choice(self, clean_text, from_number=from_number, now=now)
        if menu_result is not None:
            return menu_result

        return self._focus_or_general(clean_text, from_number=from_number, now=now)

    def _focus_or_general(
        self, clean_text: str, *, from_number: str, now: datetime
    ) -> WhatsAppInboundResult:
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

    def _triage_result(
        self, clean_text: str, *, from_number: str, now: datetime
    ) -> WhatsAppInboundResult | None:
        """Derivación a bienestar y redirección clínica también por WhatsApp.

        Solo texto curado (sin LLM en este canal) y sin datos del usuario
        en el payload — la unidad y su teléfono son configuración que el
        propio usuario registró. Corre después de la autenticación de
        remitente: un número no emparejado nunca llega acá.
        """
        result = triage_turn(
            clean_text,
            recent_low_mood_days=count_recent_low_mood_days(self._db, now),
        )
        if result.level is TriageLevel.CLINICAL_SCOPE:
            return self._reply(
                to=from_number,
                action="SCOPE_REDIRECT",
                response_text=build_scope_redirect_response(),
            )
        if result.level is TriageLevel.WELLBEING_REFERRAL:
            channels = UserConfigService(self._db).get_channels()
            return self._reply(
                to=from_number,
                action="WELLBEING_REFERRAL",
                response_text=build_wellbeing_referral_response(
                    unit_name=channels.wellbeing_unit_name,
                    unit_phone=channels.wellbeing_unit_phone,
                ),
            )
        # SUPPORTIVE/ELEVATED/ACADEMIC siguen el flujo normal del canal
        # (menú, foco, respuesta general) — acá no hay LLM que matizar.
        return None

    # ------------------------------------------------------------------
    # Infraestructura compartida por los handlers
    # ------------------------------------------------------------------

    def _is_authorized_sender(self, from_number: str) -> bool:
        """True si `from_number` es el dueño emparejado, o si aún no hay
        número emparejado (onboarding incompleto — no bloquear ese flujo)."""
        paired = UserConfigService(self._db).get_channels().whatsapp_number
        if not paired:
            return True
        return _digits_only(paired) == _digits_only(from_number)

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

    def _store_pending(self, number: str, payload: dict[str, object]) -> None:
        self._db.config.set(pending_key(number), json.dumps(payload, ensure_ascii=False))

    def _read_pending(self, number: str, *, now: datetime) -> dict[str, object] | None:
        raw = self._db.config.get(pending_key(number))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._clear_pending(number)
            return None
        if not isinstance(payload, dict):
            self._clear_pending(number)
            return None
        expires_at = payload.get("expires_at")
        if isinstance(expires_at, str) and datetime.fromisoformat(expires_at) <= now:
            self._clear_pending(number)
            return None
        return payload

    def _clear_pending(self, number: str) -> None:
        self._db.config.delete(pending_key(number))


def _digits_only(number: str) -> str:
    return "".join(char for char in number if char.isdigit())
