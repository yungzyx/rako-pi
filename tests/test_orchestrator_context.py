from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database
from db.types import EmotionalStateRecord, TaskStatus
from emotion.types import EmotionalVector
from orchestrator.context import build_user_context, count_recent_low_mood_days
from product.user_config import UserConfigService
from productivity.focus import create_focus_task


def test_build_user_context_uses_tasks_and_normal_user_memory(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("leer papers", now - timedelta(hours=1)))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=now)
    db.tasks.create(create_focus_task("programar", now))
    config = UserConfigService(db)
    config.add_memory(text="Prefiere bloques de 25 minutos", category="routine", now=now)
    config.update_consent({"sensitive_memory_enabled": True}, now=now)
    config.add_memory(
        text="Dato sensible que no debe salir",
        category="boundary",
        sensitivity="sensitive",
        now=now,
    )

    context = build_user_context(
        db,
        now,
        recent_conversation=("Usuario: sigamos",),
    )

    assert context.pending_task_count == 1
    assert context.recent_completion_count == 1
    assert context.recent_conversation == ("Usuario: sigamos",)
    assert context.user_memory == ("routine: Prefiere bloques de 25 minutos",)
    assert "Dato sensible" not in " ".join(context.user_memory)


def _low_mood_sample(record_id: str, at: datetime) -> EmotionalStateRecord:
    return EmotionalStateRecord(
        id=record_id,
        at=at,
        vector=EmotionalVector(valence=-0.55, arousal=0.55, dominance=0.35),
        trigger_event="whatsapp_checkin",
        confidence=0.7,
    )


def test_count_recent_low_mood_days_counts_distinct_days(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    # Dos muestras el mismo día cuentan como UN día; tres días distintos → 3.
    db.emotional_states.append(_low_mood_sample("a", now - timedelta(days=1, hours=2)))
    db.emotional_states.append(_low_mood_sample("b", now - timedelta(days=1, hours=1)))
    db.emotional_states.append(_low_mood_sample("c", now - timedelta(days=3)))
    db.emotional_states.append(_low_mood_sample("d", now - timedelta(days=5)))

    assert count_recent_low_mood_days(db, now) == 3


def test_count_recent_low_mood_days_ignores_neutral_and_old_samples(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    db.emotional_states.append(
        EmotionalStateRecord(
            id="neutral",
            at=now - timedelta(days=1),
            vector=EmotionalVector(valence=0.1, arousal=0.3, dominance=0.5),
            trigger_event="whatsapp_checkin",
            confidence=0.7,
        )
    )
    db.emotional_states.append(_low_mood_sample("old", now - timedelta(days=10)))

    assert count_recent_low_mood_days(db, now) == 0
