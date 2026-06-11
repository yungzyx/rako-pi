"""Progress summaries for app and WhatsApp.

The first version derives progress from tasks only, so it works with the
current schema. A future focus-session table can enrich minutes/blocks without
changing the public summary shape.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal

from db.database import Database
from db.types import Task, TaskStatus

ProgressPeriod = Literal["today", "week"]


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    period: ProgressPeriod
    start: str
    end: str
    tasks_created: int
    tasks_completed: int
    tasks_cancelled: int
    pending_task_count: int
    active_task_count: int
    completion_titles: tuple[str, ...]
    next_task_title: str | None
    message: str


def build_progress_summary(
    db: Database,
    *,
    now: datetime | None = None,
    period: ProgressPeriod = "today",
) -> ProgressSummary:
    now = _ensure_aware(now or datetime.now(UTC))
    start, end = _period_bounds(now, period)
    recent_tasks = db.tasks.list_recent(limit=100)
    in_period = [task for task in recent_tasks if start <= _ensure_aware(task.created_at) <= end]
    completed = [
        task
        for task in recent_tasks
        if task.status is TaskStatus.DONE
        and task.completed_at is not None
        and start <= _ensure_aware(task.completed_at) <= end
    ]
    cancelled = [
        task
        for task in recent_tasks
        if task.status is TaskStatus.CANCELLED
        and task.completed_at is not None
        and start <= _ensure_aware(task.completed_at) <= end
    ]
    pending = db.tasks.list_pending()
    next_task = _pick_next_task(pending)
    summary = ProgressSummary(
        period=period,
        start=start.isoformat(),
        end=end.isoformat(),
        tasks_created=len(in_period),
        tasks_completed=len(completed),
        tasks_cancelled=len(cancelled),
        pending_task_count=len(pending),
        active_task_count=sum(1 for task in pending if task.status is TaskStatus.IN_PROGRESS),
        completion_titles=tuple(task.title for task in completed[:3]),
        next_task_title=next_task.title if next_task else None,
        message="",
    )
    return ProgressSummary(**{**asdict(summary), "message": _build_progress_message(summary)})


def progress_summary_to_dict(summary: ProgressSummary) -> dict[str, object]:
    return asdict(summary)


def build_external_progress_message(summary: ProgressSummary) -> str:
    """Privacy-safe message for external channels such as WhatsApp.

    It intentionally avoids task titles. Detailed titles stay available through
    the local authenticated API.
    """
    period_text = "hoy" if summary.period == "today" else "esta semana"
    if summary.tasks_completed > 0:
        task_word = "tarea" if summary.tasks_completed == 1 else "tareas"
        base = f"{period_text.capitalize()} completaste {summary.tasks_completed} {task_word}."
    elif summary.active_task_count > 0:
        base = f"{period_text.capitalize()} tienes una tarea en marcha."
    else:
        base = f"{period_text.capitalize()} todavía no hay tareas completadas."

    if summary.pending_task_count > 0:
        return f"{base} Hay un siguiente paso disponible cuando quieras retomarlo."
    return f"{base} Podemos elegir una tarea pequeña para partir."


def _period_bounds(now: datetime, period: ProgressPeriod) -> tuple[datetime, datetime]:
    today = now.date()
    start_day = today if period == "today" else today - timedelta(days=today.weekday())
    start = datetime.combine(start_day, time.min, tzinfo=now.tzinfo)
    return start, now


def _pick_next_task(tasks: list[Task]) -> Task | None:
    if not tasks:
        return None
    active = [task for task in tasks if task.status is TaskStatus.IN_PROGRESS]
    return active[0] if active else tasks[0]


def _build_progress_message(summary: ProgressSummary) -> str:
    period_text = "hoy" if summary.period == "today" else "esta semana"
    if summary.tasks_completed > 0:
        base = f"{period_text.capitalize()} completaste {summary.tasks_completed} tarea"
        if summary.tasks_completed != 1:
            base += "s"
        if summary.completion_titles:
            base += f": {', '.join(summary.completion_titles)}"
        base += "."
    elif summary.active_task_count > 0:
        base = f"{period_text.capitalize()} ya tienes una tarea en marcha."
    else:
        base = f"{period_text.capitalize()} todavía no hay tareas completadas."

    if summary.next_task_title:
        return f"{base} Siguiente paso sugerido: {summary.next_task_title}."
    return f"{base} Podemos elegir una tarea pequeña para partir."


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
