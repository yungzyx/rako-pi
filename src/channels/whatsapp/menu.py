"""Menú de acciones del canal WhatsApp (opciones 1-6)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from channels.whatsapp.config_commands import config_status_message
from channels.whatsapp.pending_flows import pending_expires_at
from channels.whatsapp.results import WhatsAppInboundResult
from product.user_config import UserConfigService
from productivity.progress import build_external_progress_message, build_progress_summary
from productivity.study_plan import build_external_study_plan_message, build_study_plan

if TYPE_CHECKING:
    from channels.whatsapp.service import WhatsAppService

MENU_TEXT = (
    "¿Qué hacemos ahora?\n"
    "1. Elegir una tarea corta\n"
    "2. Foco de 25 minutos\n"
    "3. Revisar progreso\n"
    "4. Check-in de ánimo\n"
    "5. Plan rápido\n"
    "6. Configuración"
)

_TASK_TRIGGERS = frozenset({"1", "tarea", "tarea corta"})
_FOCUS_TRIGGERS = frozenset({"2", "foco", "pomodoro"})
_PROGRESS_TRIGGERS = frozenset({"3", "progreso", "avance"})
_MOOD_TRIGGERS = frozenset({"4", "ánimo", "animo", "mood"})
_PLAN_TRIGGERS = frozenset({"5", "plan", "plan rápido", "plan rapido", "planear"})
_CONFIG_TRIGGERS = frozenset({"6", "configuración", "configuracion", "ajustes"})


def handle_menu_choice(
    service: WhatsAppService, text: str, *, from_number: str, now: datetime
) -> WhatsAppInboundResult | None:
    normalized = text.strip().lower()
    if normalized in _TASK_TRIGGERS:
        return _suggest_short_task(service, from_number=from_number)
    if normalized in _FOCUS_TRIGGERS:
        service._store_pending(
            from_number, {"action": "focus_setup", "expires_at": pending_expires_at(now)}
        )
        return service._reply(
            to=from_number,
            action="MENU_FOCUS",
            response_text="Dime la actividad y duración, por ejemplo: estudiar cálculo 25 minutos.",
        )
    if normalized in _PROGRESS_TRIGGERS:
        summary = build_progress_summary(service._db, now=now, period="today")
        return service._reply(
            to=from_number,
            action="MENU_PROGRESS",
            response_text=build_external_progress_message(summary),
        )
    if normalized in _MOOD_TRIGGERS:
        service._store_pending(
            from_number, {"action": "mood_checkin", "expires_at": pending_expires_at(now)}
        )
        return service._reply(
            to=from_number,
            action="MENU_MOOD",
            response_text="Dime rápido cómo estás: bien, normal o bajo.",
        )
    if normalized in _PLAN_TRIGGERS:
        plan = build_study_plan(service._db, now=now)
        return service._reply(
            to=from_number,
            action="MENU_PLAN",
            response_text=build_external_study_plan_message(plan),
        )
    if normalized in _CONFIG_TRIGGERS:
        return service._reply(
            to=from_number,
            action="CONFIG_STATUS",
            response_text=config_status_message(UserConfigService(service._db)),
        )
    return None


def _suggest_short_task(service: WhatsAppService, *, from_number: str) -> WhatsAppInboundResult:
    next_task = service._db.tasks.list_pending()
    response = (
        "Partamos chico: abre tu siguiente tarea pendiente y haz solo el primer paso durante 10 minutos."
        if next_task
        else "No veo tareas pendientes. Dime una tarea y la convertimos en un primer paso de 10 minutos."
    )
    return service._reply(to=from_number, action="MENU_TASK", response_text=response)
