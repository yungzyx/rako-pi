"""Proactive coaching decisions for external check-ins.

The recommendation is intentionally privacy-safe: it may include counts and
general next actions, but never raw transcripts, task titles, or emotion values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from db.database import Database
from productivity.progress import build_progress_summary

CoachingKind = Literal[
    "LOW_MOOD_SUPPORT",
    "PROGRESS_CELEBRATION",
    "ACTIVE_TASK_NUDGE",
    "NEXT_STEP_NUDGE",
    "PLANNING_NUDGE",
]


@dataclass(frozen=True, slots=True)
class CoachingRecommendation:
    kind: CoachingKind
    text: str
    metadata: dict[str, object]


def build_coaching_recommendation(
    db: Database,
    *,
    now: datetime | None = None,
    include_progress: bool = True,
) -> CoachingRecommendation:
    now = _ensure_aware(now or datetime.now(UTC))
    recent_mood = db.emotional_states.list_in_window(end=now, lookback=timedelta(hours=12))
    if recent_mood and recent_mood[-1].vector.valence <= -0.35:
        return CoachingRecommendation(
            kind="LOW_MOOD_SUPPORT",
            text=(
                "Hoy bajemos la exigencia. Te propongo partir con 10 minutos suaves "
                "o elegir una sola tarea pequeña."
            ),
            metadata={"reason": "recent_low_mood"},
        )

    summary = build_progress_summary(db, now=now, period="today")
    if include_progress and summary.tasks_completed > 0:
        task_word = "tarea" if summary.tasks_completed == 1 else "tareas"
        return CoachingRecommendation(
            kind="PROGRESS_CELEBRATION",
            text=(
                f"Buen avance: hoy completaste {summary.tasks_completed} {task_word}. "
                "Podemos cerrar con un bloque corto o dejar listo el siguiente paso."
            ),
            metadata={
                "reason": "completed_tasks_today",
                "tasks_completed": summary.tasks_completed,
            },
        )

    if summary.active_task_count > 0:
        return CoachingRecommendation(
            kind="ACTIVE_TASK_NUDGE",
            text=(
                "Tienes una tarea en marcha. Si quieres, hacemos un bloque de 25 minutos "
                "para retomarla sin pensar demasiado."
            ),
            metadata={"reason": "active_task"},
        )

    if summary.pending_task_count > 0:
        return CoachingRecommendation(
            kind="NEXT_STEP_NUDGE",
            text=(
                "Hay un siguiente paso disponible. ¿Quieres que lo convirtamos en "
                "un bloque corto de foco?"
            ),
            metadata={"reason": "pending_tasks", "pending_task_count": summary.pending_task_count},
        )

    return CoachingRecommendation(
        kind="PLANNING_NUDGE",
        text=(
            "No veo tareas pendientes. Podemos definir una meta chica para hoy y partir "
            "con el primer paso."
        ),
        metadata={"reason": "no_pending_tasks"},
    )


def coaching_recommendation_to_dict(
    recommendation: CoachingRecommendation,
) -> dict[str, object]:
    return asdict(recommendation)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
