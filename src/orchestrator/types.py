"""Tipos compartidos del orquestador."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class UserContext:
    """Contexto agregado del usuario que se inyecta al prompt.

    Privacidad: cero PII. No incluye nombre, ID, ni vector emocional crudo.
    Solo agregados que ayudan al LLM a calibrar el tono.
    """

    pending_task_count: int
    recent_completion_count: int
    robot_level: int
    time_of_day: str
    recent_mood_summary: str | None
    recent_conversation: tuple[str, ...] = ()
    user_memory: tuple[str, ...] = ()
    # Instrucción de tono para el turno (p.ej. cuando el triage detectó
    # estrés académico). Es una instrucción fija — NO contiene datos del
    # usuario, así que no cambia qué información sale hacia el LLM.
    support_hint: str | None = None


def default_user_context(
    now: datetime,
    *,
    recent_conversation: Iterable[str] = (),
) -> UserContext:
    """Contexto mínimo basado solo en la hora — para usar cuando todavía
    no tenemos estado real del usuario en SQLite (e.g. demos, primer turn)."""
    hour = now.hour
    if 6 <= hour < 12:
        tod = "mañana"
    elif 12 <= hour < 19:
        tod = "tarde"
    else:
        tod = "noche"
    return UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=1,
        time_of_day=tod,
        recent_mood_summary=None,
        recent_conversation=tuple(recent_conversation),
        user_memory=(),
    )
