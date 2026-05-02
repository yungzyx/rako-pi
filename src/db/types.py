"""Entidades del estado local.

Inmutables (`frozen=True`). Los repositorios devuelven instancias nuevas
en cada operación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from emotion.types import EmotionalVector
from safety.types import EmotionalSample


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskStatus(Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskSource(Enum):
    VOICE = "VOICE"
    APP = "APP"
    PROACTIVE = "PROACTIVE"


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    title: str
    description: str | None
    parent_id: str | None
    status: TaskStatus
    created_at: datetime
    completed_at: datetime | None
    source: TaskSource


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


class InteractionType(Enum):
    USER_VOICE = "USER_VOICE"
    ROBOT_RESPONSE = "ROBOT_RESPONSE"
    PROACTIVE = "PROACTIVE"
    CRISIS = "CRISIS"


@dataclass(frozen=True, slots=True)
class Interaction:
    id: str
    timestamp: datetime
    type: InteractionType
    transcription_excerpt: str | None
    emotion: EmotionalVector | None
    response_id: str | None
    response_text: str | None


# ---------------------------------------------------------------------------
# Emotional state records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EmotionalStateRecord:
    id: str
    at: datetime
    vector: EmotionalVector
    trigger_event: str | None
    confidence: float

    def to_sample(self) -> EmotionalSample:
        return EmotionalSample(vector=self.vector, at=self.at)


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Achievement:
    id: str
    type: str
    earned_at: datetime
    robot_level_after: int


# ---------------------------------------------------------------------------
# Crisis journal (consumido por safety/protocol via Protocol type)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CrisisJournalEntry:
    id: str
    detected_at: datetime
    level: str
    reasons: tuple[str, ...]
    response_id: str | None
    contact_notified: bool
    recorded_at: datetime
