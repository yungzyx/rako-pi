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
_NATURAL_ACTIVITY_RE = re.compile(
    r"\b(?:voy a|quiero|necesito|tengo que)\s+(?P<title>[\wáéíóúüñÁÉÍÓÚÜÑ ]+?)\s+(?:por\s+|durante\s+)?\d{1,3}\s*(?:minutos?|mins?|m)\b",
    re.IGNORECASE,
)
_START_HINTS = (
    "voy a empezar",
    "empezar con",
    "empezar una tarea",
    "hacer un pomodoro",
    "hacer",
    "avanzar",
    "ordenar",
    "limpiar",
    "leer",
    "escribir",
    "programar",
    "practicar",
    "preparar",
    "repasar",
    "hazme un pomodoro",
    "pomodoro",
    "focus",
    "foco",
    "estudiar",
    "trabajar en",
    # Avoid broad verbs like "quiero", "necesito" or "tengo que" as
    # stand-alone focus triggers; crisis/scope text must never become a timer.
)
_ASSISTANT_INVOCATION_RE = re.compile(
    r"^(?:oye|hola|hey)?\s*(?:rako|raco|racko|rackle|raquel)\b[\s,;:.-]*",
    re.IGNORECASE,
)
_LOW_VALUE_TITLES = {"que", "qué", "eso", "algo", "pomodoro", "foco", "tarea"}
_UNSAFE_FOCUS_PATTERNS = (
    "matar",
    "matarme",
    "suicidar",
    "suicidarme",
    "morir",
    "morirme",
    "hacer dano",
    "hacer daño",
    "hacerme dano",
    "hacerme daño",
    "hacerle dano",
    "hacerle daño",
    "lastimar",
    "lastimarme",
    "herir",
    "cortar",
    "cortarme",
    "quemar",
    "quemarme",
    "cloro",
    "veneno",
    "arma",
    "violaron",
    "abuso sexual",
)
_STOPWORDS = (
    "oye rako",
    "oye raco",
    "hola rako",
    "hola raco",
    "hey rako",
    "hey raco",
    "rako",
    "raco",
    "racko",
    "rackle",
    "raquel",
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
    duration_was_explicit: bool = False


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
    text = _strip_assistant_invocation(_normalize(transcript))
    if _contains_unsafe_focus_language(text):
        return FocusIntent(should_start=False, task_title=None, minutes=_DEFAULT_FOCUS_MINUTES)
    explicit_duration = _DURATION_RE.search(text) is not None
    should_start = any(hint in text for hint in _START_HINTS)
    minutes = _extract_minutes(text)
    title = _extract_task_title(text) if should_start else None
    return FocusIntent(
        should_start=should_start,
        task_title=title,
        minutes=minutes,
        duration_was_explicit=explicit_duration,
    )


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
    natural_match = _NATURAL_ACTIVITY_RE.search(title)
    if natural_match is not None:
        natural_title = _clean_natural_activity_title(natural_match.group("title"))
        if natural_title:
            return natural_title
    title = _DURATION_RE.sub(" ", title)
    para_match = re.search(r"\bpara\s+(?P<title>.+)$", title)
    if para_match is not None:
        para_title = _clean_title_words(para_match.group("title"))
        if para_title:
            return para_title
    for phrase in (
        "voy a empezar con",
        "voy a empezar",
        "voy a",
        "quiero",
        "necesito",
        "tengo que",
        "avanzar en",
        "avanzar",
        "ordenar",
        "limpiar",
        "leer",
        "escribir",
        "programar",
        "practicar",
        "preparar",
        "repasar",
        "empezar con",
        "trabajar en",
        "estudiar para",
        "estudiar",
        "hazme",
        "hacer",
        "de",
        "para",
        "por",
        "durante",
    ):
        title = title.replace(phrase, " ")
    return _clean_title_words(title)


def _clean_natural_activity_title(title: str) -> str | None:
    clean = _clean_title_words(title)
    if clean is None:
        return None
    original = clean
    remove_action_prefixes = not original.startswith(("leer ", "escribir "))
    for prefix in (
        "empezar con ",
        "empezar ",
        "programar ",
        "limpiar ",
        "ordenar ",
        "leer ",
        "escribir ",
        "practicar ",
        "preparar ",
        "repasar ",
    ):
        if clean.startswith(prefix):
            if prefix in {"leer ", "escribir "} and not remove_action_prefixes:
                continue
            clean = clean.removeprefix(prefix).strip()
            break
    clean = clean.removeprefix("el ").removeprefix("la ").strip()
    if original != clean and clean.startswith("estudiar "):
        clean = clean.removeprefix("estudiar ").strip()
    if clean.lower() in _LOW_VALUE_TITLES:
        return None
    return clean or None


def _clean_title_words(title: str) -> str | None:
    title = re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ]+", " ", title)
    words = [w for w in title.split() if w]
    if not words:
        return None
    cleaned = " ".join(words[:12]).strip()
    if cleaned.lower() in _LOW_VALUE_TITLES:
        return None
    return cleaned


def _strip_assistant_invocation(text: str) -> str:
    return _ASSISTANT_INVOCATION_RE.sub("", text).strip()


def _contains_unsafe_focus_language(text: str) -> bool:
    return any(pattern in text for pattern in _UNSAFE_FOCUS_PATTERNS)


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())
