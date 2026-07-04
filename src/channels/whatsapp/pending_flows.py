"""Estado pendiente de corta vida (foco, ánimo, borrado) por WhatsApp."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from channels.whatsapp.mood import classify_mood, mood_response, store_mood
from channels.whatsapp.results import WhatsAppInboundResult
from product.user_config import UserConfigService
from productivity.runtime import maybe_start_focus_from_transcript

if TYPE_CHECKING:
    from channels.whatsapp.service import WhatsAppService

PENDING_TTL_SECONDS = 15 * 60
_DELETE_CONFIRMATION_PHRASE = "confirmar borrar mis datos"


def pending_key(number: str) -> str:
    safe_number = "".join(char for char in number if char.isalnum())
    return f"whatsapp.pending.{safe_number}"


def pending_expires_at(now: datetime) -> str:
    return (now + timedelta(seconds=PENDING_TTL_SECONDS)).isoformat()


def extract_minutes(text: str) -> int | None:
    for token in text.replace(",", " ").split():
        if token.isdigit():
            minutes = int(token)
            if 1 <= minutes <= 180:
                return minutes
    return None


def looks_like_duration_only(text: str) -> bool:
    tokens = [token for token in text.lower().replace(",", " ").split() if token]
    if not tokens:
        return False
    allowed = {"min", "mins", "minuto", "minutos"}
    return all(token.isdigit() or token in allowed for token in tokens)


def handle_pending(
    service: WhatsAppService, text: str, *, from_number: str, now: datetime
) -> WhatsAppInboundResult | None:
    pending = service._read_pending(from_number, now=now)
    if pending is None:
        return None
    action = pending.get("action")
    if action == "mood_checkin":
        return _resolve_pending_mood(service, text, from_number=from_number, now=now)
    if action == "focus_setup":
        return handle_pending_focus(
            service, text, from_number=from_number, now=now, pending=pending
        )
    if action == "delete_user_data":
        return _resolve_pending_delete(service, text, from_number=from_number)
    return None


def _resolve_pending_mood(
    service: WhatsAppService, text: str, *, from_number: str, now: datetime
) -> WhatsAppInboundResult:
    mood = classify_mood(text)
    if mood is None:
        return service._reply(
            to=from_number,
            action="MENU_MOOD",
            response_text="Respóndeme con una de estas tres: bien, normal o bajo.",
        )
    service._clear_pending(from_number)
    store_mood(service._db, mood=mood, now=now)
    return service._reply(
        to=from_number,
        action="MOOD_RECORDED",
        response_text=mood_response(mood),
        stored_mood=mood,
    )


def _resolve_pending_delete(
    service: WhatsAppService, text: str, *, from_number: str
) -> WhatsAppInboundResult:
    if text.lower().strip() != _DELETE_CONFIRMATION_PHRASE:
        return service._reply(
            to=from_number,
            action="DELETE_USER_DATA_CONFIRM",
            response_text=(
                "No borré nada. Para confirmar, responde exactamente: confirmar borrar mis datos."
            ),
        )
    UserConfigService(service._db).delete_user_data()
    service._clear_pending(from_number)
    return service._reply(
        to=from_number,
        action="USER_DATA_DELETED",
        response_text=(
            "Listo, borré todo tu historial en este dispositivo: perfil, "
            "configuración, memoria, tareas, interacciones y estados de ánimo."
        ),
    )


def handle_pending_focus(
    service: WhatsAppService,
    text: str,
    *,
    from_number: str,
    now: datetime,
    pending: dict[str, object],
) -> WhatsAppInboundResult:
    minutes = extract_minutes(text)
    if minutes is not None and looks_like_duration_only(text):
        return _focus_with_duration_only(
            service, minutes=minutes, pending=pending, from_number=from_number, now=now
        )
    return _focus_with_activity_text(
        service, text, pending=pending, from_number=from_number, now=now
    )


def _focus_with_duration_only(
    service: WhatsAppService,
    *,
    minutes: int,
    pending: dict[str, object],
    from_number: str,
    now: datetime,
) -> WhatsAppInboundResult:
    saved_title = pending.get("title")
    if isinstance(saved_title, str) and saved_title.strip():
        focus = maybe_start_focus_from_transcript(
            f"estudiar {saved_title} {minutes} minutos", db=service._db, now=now
        )
        if focus is not None and focus.session is not None:
            service._clear_pending(from_number)
            return service._reply(
                to=from_number,
                action="FOCUS",
                response_text=focus.response_text,
                focus_session_id=focus.session.id,
            )
    service._store_pending(
        from_number,
        {"action": "focus_setup", "minutes": minutes, "expires_at": pending_expires_at(now)},
    )
    return service._reply(
        to=from_number,
        action="MENU_FOCUS",
        response_text=f"Perfecto, {minutes} minutos. ¿Qué actividad hacemos?",
    )


def _focus_with_activity_text(
    service: WhatsAppService,
    text: str,
    *,
    pending: dict[str, object],
    from_number: str,
    now: datetime,
) -> WhatsAppInboundResult:
    saved_minutes = pending.get("minutes")
    focus_text = text
    if isinstance(saved_minutes, int):
        focus_text = f"{text} {saved_minutes} minutos"

    focus = maybe_start_focus_from_transcript(focus_text, db=service._db, now=now)
    if focus is not None and focus.session is not None:
        service._clear_pending(from_number)
        return service._reply(
            to=from_number,
            action="FOCUS",
            response_text=focus.response_text,
            focus_session_id=focus.session.id,
        )
    if focus is not None and focus.needs_duration:
        service._store_pending(
            from_number,
            {
                "action": "focus_setup",
                "title": focus.suggested_title,
                "expires_at": pending_expires_at(now),
            },
        )
        return service._reply(
            to=from_number, action="MENU_FOCUS", response_text=focus.response_text
        )
    return _capture_title_or_hint(service, text, from_number=from_number, now=now)


def _capture_title_or_hint(
    service: WhatsAppService, text: str, *, from_number: str, now: datetime
) -> WhatsAppInboundResult:
    clean_title = text.strip()
    if clean_title and extract_minutes(clean_title) is None:
        service._store_pending(
            from_number,
            {
                "action": "focus_setup",
                "title": clean_title,
                "expires_at": pending_expires_at(now),
            },
        )
        return service._reply(
            to=from_number,
            action="MENU_FOCUS",
            response_text=(
                f"Dale. ¿Por cuántos minutos quieres hacer {clean_title}? "
                "Si quieres, te recomiendo 25 minutos para partir."
            ),
        )
    return service._reply(
        to=from_number,
        action="MENU_FOCUS",
        response_text="Dime algo como: estudiar cálculo 25 minutos.",
    )
