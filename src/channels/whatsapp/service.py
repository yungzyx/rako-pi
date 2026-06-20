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
from productivity.coaching import build_coaching_recommendation
from productivity.progress import (
    ProgressPeriod,
    build_external_progress_message,
    build_progress_summary,
)
from productivity.runtime import maybe_start_focus_from_transcript
from productivity.study_plan import build_external_study_plan_message, build_study_plan
from safety.detector import detect_crisis
from safety.responses import pick_response
from safety.types import CrisisInput, CrisisLevel

_LAST_CHECKIN_KEY = "whatsapp.last_checkin"
_PENDING_TTL_SECONDS = 15 * 60


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

    def send_smart_checkin(
        self,
        *,
        to: str,
        now: datetime | None = None,
    ) -> WhatsAppOutboundMessage:
        now = _ensure_aware(now or datetime.now(UTC))
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
        now = _ensure_aware(now or datetime.now(UTC))
        if not UserConfigService(self._db).whatsapp_can_send():
            return self._consent_required(to=to, now=now)
        text = (
            "¿Qué hacemos ahora?\n"
            "1. Elegir una tarea corta\n"
            "2. Foco de 25 minutos\n"
            "3. Revisar progreso\n"
            "4. Check-in de ánimo\n"
            "5. Plan rápido\n"
            "6. Configuración"
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
            self._clear_pending(from_number)
            response = pick_response(crisis_signal)
            return self._reply(
                to=from_number,
                action="CRISIS",
                response_text=response.text,
                crisis=True,
            )

        pending_result = self._handle_pending(clean_text, from_number=from_number, now=now)
        if pending_result is not None:
            return pending_result

        memory_result = self._handle_memory_command(clean_text, from_number=from_number)
        if memory_result is not None:
            return memory_result

        config_result = self._handle_config_command(clean_text, from_number=from_number, now=now)
        if config_result is not None:
            return config_result

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
            self._store_pending(
                from_number,
                {"action": "focus_setup", "expires_at": _pending_expires_at(now)},
            )
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
            self._store_pending(
                from_number,
                {"action": "mood_checkin", "expires_at": _pending_expires_at(now)},
            )
            return self._reply(
                to=from_number,
                action="MENU_MOOD",
                response_text="Dime rápido cómo estás: bien, normal o bajo.",
            )
        if normalized in {"5", "plan", "plan rápido", "plan rapido", "planear"}:
            plan = build_study_plan(self._db, now=now)
            return self._reply(
                to=from_number,
                action="MENU_PLAN",
                response_text=build_external_study_plan_message(plan),
            )
        if normalized in {"6", "configuración", "configuracion", "ajustes"}:
            return self._reply(
                to=from_number,
                action="CONFIG_STATUS",
                response_text=_config_status_message(UserConfigService(self._db)),
            )
        return None

    def _handle_memory_command(
        self,
        text: str,
        *,
        from_number: str,
    ) -> WhatsAppInboundResult | None:
        normalized = text.lower().strip()
        config = UserConfigService(self._db)
        for prefix in ("rako recuerda que ", "recuerda que ", "rako recuerda ", "recuerda "):
            if normalized.startswith(prefix):
                original_text = text[len(prefix) :].strip()
                if not original_text:
                    return self._reply(
                        to=from_number,
                        action="MEMORY_HELP",
                        response_text="Dime algo concreto, por ejemplo: recuerda que prefiero bloques de 25 minutos.",
                    )
                memory = config.add_memory(text=original_text, category="preference")
                return self._reply(
                    to=from_number,
                    action="MEMORY_ADDED",
                    response_text=f"Listo, lo guardé: {memory.text}",
                )

        if normalized in {
            "memoria",
            "mis recuerdos",
            "que sabes de mi",
            "qué sabes de mí",
            "qué sabes de mi",
        }:
            memories = config.list_memory()
            if not memories:
                return self._reply(
                    to=from_number,
                    action="MEMORY_LIST",
                    response_text="Todavía no tengo recuerdos guardados sobre tus preferencias.",
                )
            lines = [f"- {memory.text}" for memory in memories[:5]]
            return self._reply(
                to=from_number,
                action="MEMORY_LIST",
                response_text="Esto tengo guardado:\n" + "\n".join(lines),
            )

        for prefix in ("rako olvida que ", "olvida que ", "rako olvida ", "olvida "):
            if normalized.startswith(prefix):
                query = text[len(prefix) :].strip()
                if not query:
                    return self._reply(
                        to=from_number,
                        action="MEMORY_DELETE_HELP",
                        response_text="Dime qué recuerdo borrar, por ejemplo: olvida bloques de 25 minutos.",
                    )
                deleted = _delete_memory_matching(config, query)
                if deleted:
                    return self._reply(
                        to=from_number,
                        action="MEMORY_DELETED",
                        response_text="Listo, borré ese recuerdo.",
                    )
                return self._reply(
                    to=from_number,
                    action="MEMORY_NOT_FOUND",
                    response_text="No encontré un recuerdo que coincida con eso.",
                )
        return None

    def _handle_config_command(
        self,
        text: str,
        *,
        from_number: str,
        now: datetime,
    ) -> WhatsAppInboundResult | None:
        normalized = text.lower().strip()
        config = UserConfigService(self._db)
        if normalized in {
            "pausar mensajes",
            "pausa mensajes",
            "no me escribas",
            "silenciar rako",
            "silenciar",
        }:
            config.update_consent({"proactive_messages_enabled": False})
            return self._reply(
                to=from_number,
                action="MESSAGES_PAUSED",
                response_text=(
                    "Listo, pausé los mensajes proactivos. "
                    "Puedes escribirme igual cuando quieras. Para volver: reanudar mensajes."
                ),
            )

        if normalized in {
            "reanudar mensajes",
            "activar mensajes",
            "volver a escribirme",
            "reactivar rako",
        }:
            if not config.whatsapp_can_send():
                return self._reply(
                    to=from_number,
                    action="CONSENT_REQUIRED",
                    response_text=(
                        "Antes necesito que WhatsApp esté activado en la configuración de Rako."
                    ),
                )
            config.update_consent({"proactive_messages_enabled": True})
            return self._reply(
                to=from_number,
                action="MESSAGES_RESUMED",
                response_text="Listo, reanudé los mensajes proactivos de estudio.",
            )

        if normalized in {"configuración", "configuracion", "ajustes", "mi configuración"}:
            return self._reply(
                to=from_number,
                action="CONFIG_STATUS",
                response_text=_config_status_message(config),
            )

        if normalized in {"exportar mis datos", "mis datos", "datos"}:
            return self._reply(
                to=from_number,
                action="USER_DATA_EXPORT",
                response_text=_compact_user_data_message(config.export_user_data()),
            )

        if normalized in {"borrar mis datos", "eliminar mis datos"}:
            self._store_pending(
                from_number,
                {"action": "delete_user_data", "expires_at": _pending_expires_at(now)},
            )
            return self._reply(
                to=from_number,
                action="DELETE_USER_DATA_CONFIRM",
                response_text=(
                    "Puedo borrar perfil, consentimiento, canales y memoria editable. "
                    "Para confirmar, responde: confirmar borrar mis datos."
                ),
            )
        return None

    def _handle_pending(
        self,
        text: str,
        *,
        from_number: str,
        now: datetime,
    ) -> WhatsAppInboundResult | None:
        pending = self._read_pending(from_number, now=now)
        if pending is None:
            return None
        action = pending.get("action")
        if action == "mood_checkin":
            mood = _classify_mood(text)
            if mood is None:
                return self._reply(
                    to=from_number,
                    action="MENU_MOOD",
                    response_text="Respóndeme con una de estas tres: bien, normal o bajo.",
                )
            self._clear_pending(from_number)
            self._store_mood(mood=mood, now=now)
            return self._reply(
                to=from_number,
                action="MOOD_RECORDED",
                response_text=_mood_response(mood),
                stored_mood=mood,
            )
        if action == "focus_setup":
            return self._handle_pending_focus(
                text, from_number=from_number, now=now, pending=pending
            )
        if action == "delete_user_data":
            if text.lower().strip() != "confirmar borrar mis datos":
                return self._reply(
                    to=from_number,
                    action="DELETE_USER_DATA_CONFIRM",
                    response_text=(
                        "No borré nada. Para confirmar, responde exactamente: "
                        "confirmar borrar mis datos."
                    ),
                )
            deleted = UserConfigService(self._db).delete_user_data()
            self._clear_pending(from_number)
            deleted_count = sum(1 for was_deleted in deleted.values() if was_deleted)
            return self._reply(
                to=from_number,
                action="USER_DATA_DELETED",
                response_text=f"Listo, borré {deleted_count} bloques de configuración personal.",
            )
        return None

    def _handle_pending_focus(
        self,
        text: str,
        *,
        from_number: str,
        now: datetime,
        pending: dict[str, object],
    ) -> WhatsAppInboundResult:
        minutes = _extract_minutes(text)
        if minutes is not None and _looks_like_duration_only(text):
            saved_title = pending.get("title")
            if isinstance(saved_title, str) and saved_title.strip():
                focus = maybe_start_focus_from_transcript(
                    f"estudiar {saved_title} {minutes} minutos",
                    db=self._db,
                    now=now,
                )
                if focus is not None and focus.session is not None:
                    self._clear_pending(from_number)
                    return self._reply(
                        to=from_number,
                        action="FOCUS",
                        response_text=focus.response_text,
                        focus_session_id=focus.session.id,
                    )
            updated = {
                "action": "focus_setup",
                "minutes": minutes,
                "expires_at": _pending_expires_at(now),
            }
            self._store_pending(from_number, updated)
            return self._reply(
                to=from_number,
                action="MENU_FOCUS",
                response_text=f"Perfecto, {minutes} minutos. ¿Qué actividad hacemos?",
            )

        saved_minutes = pending.get("minutes")
        focus_text = text
        if isinstance(saved_minutes, int):
            focus_text = f"{text} {saved_minutes} minutos"

        focus = maybe_start_focus_from_transcript(focus_text, db=self._db, now=now)
        if focus is not None and focus.session is not None:
            self._clear_pending(from_number)
            return self._reply(
                to=from_number,
                action="FOCUS",
                response_text=focus.response_text,
                focus_session_id=focus.session.id,
            )
        if focus is not None and focus.needs_duration:
            self._store_pending(
                from_number,
                {
                    "action": "focus_setup",
                    "title": focus.suggested_title,
                    "expires_at": _pending_expires_at(now),
                },
            )
            return self._reply(
                to=from_number,
                action="MENU_FOCUS",
                response_text=focus.response_text,
            )
        clean_title = text.strip()
        if clean_title and _extract_minutes(clean_title) is None:
            self._store_pending(
                from_number,
                {
                    "action": "focus_setup",
                    "title": clean_title,
                    "expires_at": _pending_expires_at(now),
                },
            )
            return self._reply(
                to=from_number,
                action="MENU_FOCUS",
                response_text=(
                    f"Dale. ¿Por cuántos minutos quieres hacer {clean_title}? "
                    "Si quieres, te recomiendo 25 minutos para partir."
                ),
            )
        return self._reply(
            to=from_number,
            action="MENU_FOCUS",
            response_text="Dime algo como: estudiar cálculo 25 minutos.",
        )

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

    def _store_pending(self, number: str, payload: dict[str, object]) -> None:
        self._db.config.set(_pending_key(number), json.dumps(payload, ensure_ascii=False))

    def _read_pending(self, number: str, *, now: datetime) -> dict[str, object] | None:
        raw = self._db.config.get(_pending_key(number))
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
        self._db.config.delete(_pending_key(number))


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


def _extract_minutes(text: str) -> int | None:
    for token in text.replace(",", " ").split():
        if token.isdigit():
            minutes = int(token)
            if 1 <= minutes <= 180:
                return minutes
    return None


def _looks_like_duration_only(text: str) -> bool:
    tokens = [token for token in text.lower().replace(",", " ").split() if token]
    if not tokens:
        return False
    allowed = {"min", "mins", "minuto", "minutos"}
    return all(token.isdigit() or token in allowed for token in tokens)


def _delete_memory_matching(config: UserConfigService, query: str) -> bool:
    clean_query = query.strip().lower()
    if not clean_query:
        return False
    for memory in config.list_memory():
        if clean_query in memory.text.lower():
            return config.delete_memory(memory.id)
    return False


def _config_status_message(config: UserConfigService) -> str:
    consent = config.get_consent()
    channels = config.get_channels()
    return (
        "Configuración actual:\n"
        f"- WhatsApp: {_yes_no(consent.whatsapp_enabled and bool(channels.whatsapp_number))}\n"
        f"- Mensajes proactivos: {_yes_no(config.proactive_messages_can_send())}\n"
        f"- Reportes de progreso: {_yes_no(config.progress_reports_can_send())}\n"
        f"- Memorias guardadas: {len(config.list_memory())}\n"
        "Comandos útiles: pausar mensajes, reanudar mensajes, exportar mis datos, borrar mis datos."
    )


def _compact_user_data_message(export: dict[str, object]) -> str:
    profile = export.get("profile")
    consent = export.get("consent")
    channels = export.get("channels")
    memory = export.get("memory")
    preferred_name = profile.get("preferred_name") if isinstance(profile, dict) else None
    university = profile.get("university") if isinstance(profile, dict) else None
    whatsapp_enabled = consent.get("whatsapp_enabled") if isinstance(consent, dict) else False
    wifi_ssid = channels.get("wifi_ssid") if isinstance(channels, dict) else None
    memory_count = len(memory) if isinstance(memory, list) else 0
    return (
        "Resumen de tus datos locales:\n"
        f"- Nombre: {preferred_name or 'sin configurar'}\n"
        f"- Universidad: {university or 'sin configurar'}\n"
        f"- WiFi guardado: {wifi_ssid or 'sin configurar'}\n"
        f"- WhatsApp activo: {_yes_no(bool(whatsapp_enabled))}\n"
        f"- Memorias: {memory_count}\n"
        "Desde la API local puedes exportar el detalle completo en /user/export."
    )


def _yes_no(value: bool) -> str:
    return "sí" if value else "no"


def _pending_key(number: str) -> str:
    safe_number = "".join(char for char in number if char.isalnum())
    return f"whatsapp.pending.{safe_number}"


def _pending_expires_at(now: datetime) -> str:
    return (now + timedelta(seconds=_PENDING_TTL_SECONDS)).isoformat()


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
