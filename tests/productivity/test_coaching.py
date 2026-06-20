from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database
from db.types import EmotionalStateRecord, Task, TaskSource, TaskStatus
from emotion.types import EmotionalVector
from productivity.coaching import build_coaching_recommendation
from productivity.focus import create_focus_task


def _now() -> datetime:
    return datetime(2026, 6, 20, 14, 0, tzinfo=UTC)


def test_coaching_prioritizes_recent_low_mood(db_conn) -> None:
    db = Database(db_conn)
    db.emotional_states.append(
        EmotionalStateRecord(
            id="mood-low",
            at=_now() - timedelta(minutes=5),
            vector=EmotionalVector(valence=-0.6, arousal=0.5, dominance=0.3),
            trigger_event="whatsapp_checkin",
            confidence=0.8,
        )
    )
    task = db.tasks.create(create_focus_task("leer capítulo privado", _now()))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=_now())

    recommendation = build_coaching_recommendation(db, now=_now())

    assert recommendation.kind == "LOW_MOOD_SUPPORT"
    assert "10 minutos suaves" in recommendation.text
    assert "leer capítulo privado" not in recommendation.text


def test_coaching_can_celebrate_progress_without_titles(db_conn) -> None:
    db = Database(db_conn)
    task = db.tasks.create(create_focus_task("preparar evaluación sensible", _now()))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=_now())

    recommendation = build_coaching_recommendation(db, now=_now())

    assert recommendation.kind == "PROGRESS_CELEBRATION"
    assert "completaste 1 tarea" in recommendation.text
    assert "preparar evaluación sensible" not in recommendation.text


def test_coaching_suppresses_progress_when_not_allowed(db_conn) -> None:
    db = Database(db_conn)
    task = db.tasks.create(create_focus_task("leer paper privado", _now()))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=_now())

    recommendation = build_coaching_recommendation(db, now=_now(), include_progress=False)

    assert recommendation.kind == "PLANNING_NUDGE"
    assert "completaste" not in recommendation.text
    assert "leer paper privado" not in recommendation.text


def test_coaching_suggests_next_step_when_tasks_are_pending(db_conn) -> None:
    db = Database(db_conn)
    db.tasks.create(
        Task(
            id="pending",
            title="resolver guía privada",
            description=None,
            parent_id=None,
            status=TaskStatus.TODO,
            created_at=_now(),
            completed_at=None,
            source=TaskSource.APP,
        )
    )

    recommendation = build_coaching_recommendation(db, now=_now())

    assert recommendation.kind == "NEXT_STEP_NUDGE"
    assert "siguiente paso" in recommendation.text
    assert "resolver guía privada" not in recommendation.text
