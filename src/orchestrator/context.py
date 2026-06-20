"""Build privacy-safe user context for LLM turns."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from db.database import Database
from db.types import TaskStatus
from orchestrator.types import UserContext, default_user_context
from product.user_config import UserConfigService


def build_user_context(
    db: Database,
    now: datetime,
    *,
    recent_conversation: Iterable[str] = (),
) -> UserContext:
    """Return aggregate context plus user-controlled non-sensitive memory.

    The LLM gets counts and normal preference memory only. Sensitive memory and
    full transcripts stay local.
    """
    base = default_user_context(now, recent_conversation=recent_conversation)
    tasks = db.tasks.list_recent(limit=100)
    pending = db.tasks.list_pending()
    recent_cutoff = now - timedelta(days=7)
    recent_completed = [
        task
        for task in tasks
        if task.status is TaskStatus.DONE
        and task.completed_at is not None
        and task.completed_at >= recent_cutoff
    ]
    return UserContext(
        pending_task_count=len(pending),
        recent_completion_count=len(recent_completed),
        robot_level=_robot_level(db),
        time_of_day=base.time_of_day,
        recent_mood_summary=_recent_mood_summary(db, now),
        recent_conversation=tuple(recent_conversation),
        user_memory=_normal_memory_lines(db),
    )


def _normal_memory_lines(db: Database) -> tuple[str, ...]:
    service = UserConfigService(db)
    memories = [
        f"{memory.category}: {memory.text}"
        for memory in service.list_memory()
        if memory.sensitivity == "normal"
    ]
    return tuple(memories[-8:])


def _robot_level(db: Database) -> int:
    achievements = db.achievements.list_all()
    if not achievements:
        return 1
    return max(1, achievements[0].robot_level_after)


def _recent_mood_summary(db: Database, now: datetime) -> str | None:
    samples = db.emotional_states.list_samples_in_window(end=now, lookback=timedelta(hours=24))
    if not samples:
        return None
    avg_valence = sum(sample.vector.valence for sample in samples) / len(samples)
    if avg_valence <= -0.35:
        return "bajo o cansado recientemente"
    if avg_valence >= 0.35:
        return "con buen ánimo recientemente"
    return "estable o neutral recientemente"
