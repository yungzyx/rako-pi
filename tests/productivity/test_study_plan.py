from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database
from db.types import EmotionalStateRecord, Task, TaskSource, TaskStatus
from emotion.types import EmotionalVector
from productivity.focus import create_focus_task
from productivity.study_plan import (
    build_external_study_plan_message,
    build_study_plan,
    study_plan_to_dict,
)


def _now() -> datetime:
    return datetime(2026, 6, 20, 15, 0, tzinfo=UTC)


def test_study_plan_prioritizes_low_energy_without_private_titles(db_conn) -> None:
    db = Database(db_conn)
    db.emotional_states.append(
        EmotionalStateRecord(
            id="low",
            at=_now() - timedelta(minutes=5),
            vector=EmotionalVector(valence=-0.6, arousal=0.4, dominance=0.3),
            trigger_event="whatsapp_checkin",
            confidence=0.8,
        )
    )
    db.tasks.create(create_focus_task("leer capítulo privado", _now()))

    plan = build_study_plan(db, now=_now())

    assert plan.kind == "LOW_ENERGY_RESET"
    assert plan.recommended_minutes == 10
    assert plan.next_task_title == "leer capítulo privado"
    assert "leer capítulo privado" not in plan.external_message
    assert "pausa breve" in build_external_study_plan_message(plan)


def test_study_plan_resumes_active_task(db_conn) -> None:
    db = Database(db_conn)
    db.tasks.create(
        Task(
            id="task-active",
            title="preparar prueba",
            description=None,
            parent_id=None,
            status=TaskStatus.IN_PROGRESS,
            created_at=_now(),
            completed_at=None,
            source=TaskSource.APP,
        )
    )

    plan = build_study_plan(db, now=_now())
    payload = study_plan_to_dict(plan)

    assert plan.kind == "RESUME_ACTIVE_TASK"
    assert plan.recommended_minutes == 25
    assert payload["next_task_title"] == "preparar prueba"
    assert "preparar prueba" not in plan.external_message


def test_study_plan_starts_pending_task_or_first_step(db_conn) -> None:
    db = Database(db_conn)

    empty_plan = build_study_plan(db, now=_now())
    db.tasks.create(
        Task(
            id="pending",
            title="resolver guía",
            description=None,
            parent_id=None,
            status=TaskStatus.TODO,
            created_at=_now(),
            completed_at=None,
            source=TaskSource.APP,
        )
    )
    pending_plan = build_study_plan(db, now=_now())

    assert empty_plan.kind == "PLAN_FIRST_STEP"
    assert empty_plan.recommended_minutes == 10
    assert pending_plan.kind == "START_PENDING_TASK"
    assert pending_plan.recommended_minutes == 15


def test_study_plan_maintains_momentum_after_completed_task(db_conn) -> None:
    db = Database(db_conn)
    task = db.tasks.create(create_focus_task("leer paper", _now()))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=_now())

    plan = build_study_plan(db, now=_now())

    assert plan.kind == "MAINTAIN_MOMENTUM"
    assert plan.mindfulness_exercise_id == "stretch_and_breathe"
