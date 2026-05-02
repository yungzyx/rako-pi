"""Tipos compartidos del orquestador."""

from __future__ import annotations

from dataclasses import dataclass


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
