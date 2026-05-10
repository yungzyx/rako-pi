"""Focus-session and task-start models.

Pure domain logic only: no timers, threads, hardware, or network calls here.
Runtime code can use these objects to start countdowns, update OLED states, and
queue safe sync/WhatsApp notifications.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4

from db.types import Task, TaskSource, TaskStatus

_DEFAULT_FOCUS_MINUTES = 25
_MIN_FOCUS_MINUTES = 1
_MAX_FOCUS_MINUTES = 180
_DURATION_RE = re.compile(r"(?P<minutes>\d{1,3})\s*(?:minutos?|mins?|m)\b", re.IGNORECASE)
_START_HINTS = (
    "voy a empezar",
    "empezar con",
    "empezar una tarea",
    "hacer un pomodoro",
    "pomodoro",
    "focus",
    "foco",
    "estudiar",
    "trabajar en",
)
_STOPWORDS = (
    "oye rako",
    "hola rako",
    "hey rako",
    "por favor",
    "un pomodoro",
    "pomodoro",
    "temporizador",
    "timer",
    "cuenta regresiva",
    "countdown",
)


class FocusSessionStatus(Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class FocusIntent:
    should_start: bool
    task_title: str | None
    minutes: int


@dataclass(frozen=True, slots=True)
class FocusSession:
    id: str
    task_id: str
    task_title: str
    started_at: datetime
    duration: timedelta
    status: FocusSessionStatus = FocusSessionStatus.RUNNING

    @property
    def ends_at(self) -> datetime:
        return self.started_at + self.duration

    def remaining_at(self, now: datetime) -> timedelta:
        remaining = self.ends_at - now
        return max(remaining, timedelta())

    def complete(self) -> FocusSession:
        return FocusSession(
            id=self.id,
            task_id=self.task_id,
            task_title=self.task_title,
            started_at=self.started_at,
            duration=self.duration,
            status=FocusSessionStatus.COMPLETED,
        )

    def cancel(self) -> FocusSession:
        return FocusSession(
            id=self.id,
            task_id=self.task_id,
            task_title=self.task_title,
            started_at=self.started_at,
            duration=self.duration,
            status=FocusSessionStatus.CANCELLED,
        )


def parse_focus_intent(transcript: str) -> FocusIntent:
    text = _normalize(transcript)
    should_start = any(hint in text for hint in _START_HINTS)
    minutes = _extract_minutes(text)
    title = _extract_task_title(text) if should_start else None
    return FocusIntent(should_start=should_start, task_title=title, minutes=minutes)


def create_focus_task(title: str, now: datetime, *, source: TaskSource = TaskSource.VOICE) -> Task:
    clean_title = title.strip() or "Sesión de foco"
    return Task(
        id=f"task_{uuid4().hex}",
        title=clean_title,
        description=None,
        parent_id=None,
        status=TaskStatus.IN_PROGRESS,
        created_at=now,
        completed_at=None,
        source=source,
    )


def start_focus_session(task: Task, now: datetime, *, minutes: int) -> FocusSession:
    bounded = max(_MIN_FOCUS_MINUTES, min(_MAX_FOCUS_MINUTES, minutes))
    return FocusSession(
        id=f"focus_{uuid4().hex}",
        task_id=task.id,
        task_title=task.title,
        started_at=now,
        duration=timedelta(minutes=bounded),
    )


def first_step_suggestion(title: str) -> str:
    title = title.strip() or "la tarea"
    return (
        f"Partamos simple: abre lo necesario para {title} y trabaja solo cinco minutos. "
        "Yo te acompaño con el temporizador."
    )


def _extract_minutes(text: str) -> int:
    match = _DURATION_RE.search(text)
    if match is None:
        return _DEFAULT_FOCUS_MINUTES
    minutes = int(match.group("minutes"))
    return max(_MIN_FOCUS_MINUTES, min(_MAX_FOCUS_MINUTES, minutes))


def _extract_task_title(text: str) -> str | None:
    title = text
    for prefix in _STOPWORDS:
        title = title.replace(prefix, " ")
    for phrase in (
        "voy a empezar con",
        "voy a empezar",
        "empezar con",
        "trabajar en",
        "estudiar",
        "hacer",
        "de",
        "por",
        "durante",
    ):
        title = title.replace(phrase, " ")
    title = _DURATION_RE.sub(" ", title)
    title = re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ]+", " ", title)
    words = [w for w in title.split() if w]
    if not words:
        return None
    return " ".join(words[:12]).strip()


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())
