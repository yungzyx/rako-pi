"""Academic planning recommendations for Rako.

The planner turns local progress and recent mood into a small next action. It
is intentionally conservative: short blocks first, no shame, and no task titles
in external messages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from db.database import Database
from productivity.mindfulness import pick_mindfulness_exercise
from productivity.progress import build_progress_summary

PlanKind = Literal[
    "LOW_ENERGY_RESET",
    "RESUME_ACTIVE_TASK",
    "START_PENDING_TASK",
    "MAINTAIN_MOMENTUM",
    "PLAN_FIRST_STEP",
]


@dataclass(frozen=True, slots=True)
class StudyPlan:
    kind: PlanKind
    recommended_minutes: int
    next_action: str
    rationale: str
    local_message: str
    external_message: str
    next_task_title: str | None
    mindfulness_exercise_id: str | None = None


def build_study_plan(
    db: Database,
    *,
    now: datetime | None = None,
) -> StudyPlan:
    now = _ensure_aware(now or datetime.now(UTC))
    mood = db.emotional_states.list_in_window(end=now, lookback=timedelta(hours=12))
    summary = build_progress_summary(db, now=now, period="today")
    next_title = summary.next_task_title

    if mood and mood[-1].vector.valence <= -0.35:
        exercise = pick_mindfulness_exercise(context="low_mood", max_minutes=3)
        return StudyPlan(
            kind="LOW_ENERGY_RESET",
            recommended_minutes=10,
            next_action="Haz una pausa breve y luego un bloque suave de 10 minutos.",
            rationale="El último check-in viene con baja energía; conviene reducir fricción.",
            local_message=(
                f"Partamos suave: {exercise.title.lower()} y después 10 minutos "
                "con una sola acción pequeña."
            ),
            external_message=(
                "Partamos suave: una pausa breve y después 10 minutos con una sola acción pequeña."
            ),
            next_task_title=next_title,
            mindfulness_exercise_id=exercise.id,
        )

    if summary.active_task_count > 0:
        return StudyPlan(
            kind="RESUME_ACTIVE_TASK",
            recommended_minutes=25,
            next_action="Retoma la tarea en marcha con un bloque de 25 minutos.",
            rationale="Ya existe una tarea activa; conviene continuar sin replantear todo.",
            local_message=_with_optional_title(
                "Retomemos lo que ya está en marcha con 25 minutos.",
                next_title,
            ),
            external_message="Retomemos lo que ya está en marcha con 25 minutos.",
            next_task_title=next_title,
        )

    if summary.pending_task_count > 0:
        return StudyPlan(
            kind="START_PENDING_TASK",
            recommended_minutes=15,
            next_action="Empieza el siguiente pendiente con 15 minutos y una meta visible.",
            rationale="Hay tareas pendientes; un bloque corto reduce la barrera de inicio.",
            local_message=_with_optional_title(
                "Hagamos 15 minutos para iniciar el siguiente pendiente.",
                next_title,
            ),
            external_message="Hagamos 15 minutos para iniciar el siguiente pendiente.",
            next_task_title=next_title,
        )

    if summary.tasks_completed > 0:
        exercise = pick_mindfulness_exercise(context="after_focus", max_minutes=2)
        return StudyPlan(
            kind="MAINTAIN_MOMENTUM",
            recommended_minutes=15,
            next_action="Cierra con una pausa corta o deja preparado el siguiente paso.",
            rationale="Ya hubo avance hoy; conviene consolidar sin sobrecargar.",
            local_message=(
                f"Buen avance. Puedes hacer {exercise.title.lower()} o dejar preparado "
                "el siguiente paso en 15 minutos."
            ),
            external_message=(
                "Buen avance. Puedes hacer una pausa breve o dejar preparado el siguiente paso."
            ),
            next_task_title=None,
            mindfulness_exercise_id=exercise.id,
        )

    return StudyPlan(
        kind="PLAN_FIRST_STEP",
        recommended_minutes=10,
        next_action="Define una meta chica y empieza con 10 minutos.",
        rationale="No hay tareas visibles; primero hay que convertir intención en acción.",
        local_message="Definamos una meta chica para hoy y partamos con 10 minutos.",
        external_message="Definamos una meta chica para hoy y partamos con 10 minutos.",
        next_task_title=None,
    )


def study_plan_to_dict(plan: StudyPlan) -> dict[str, object]:
    return asdict(plan)


def build_external_study_plan_message(plan: StudyPlan) -> str:
    return (
        f"{plan.external_message}\n"
        f"Bloque sugerido: {plan.recommended_minutes} min.\n"
        "Responde 2 si quieres iniciar foco desde WhatsApp."
    )


def _with_optional_title(message: str, title: str | None) -> str:
    if not title:
        return message
    return f"{message} Siguiente: {title}."


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
