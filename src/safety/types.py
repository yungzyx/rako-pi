"""Tipos del módulo de seguridad.

Inmutables a propósito: una señal de crisis no debe poder mutarse una
vez emitida — el orquestador, el protocolo y el journal la comparten.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from emotion.types import EmotionalVector


class PanicSource(Enum):
    PHYSICAL = auto()
    APP = auto()


class CrisisLevel(Enum):
    NONE = auto()
    ELEVATED = auto()
    CRISIS = auto()


class CrisisReason(Enum):
    PANIC_BUTTON_PHYSICAL = auto()
    PANIC_BUTTON_APP = auto()
    KEYWORDS_IDEATION = auto()
    KEYWORDS_SELFHARM = auto()
    KEYWORDS_GOODBYE = auto()
    KEYWORDS_ABUSE_SEXUAL = auto()
    KEYWORDS_HARM_OTHERS = auto()
    KEYWORDS_DANGEROUS_ACCESS = auto()
    SUSTAINED_EMOTIONAL_EXTREME = auto()
    PROLONGED_INACTIVITY_AFTER_DISTRESS = auto()
    EMOTIONAL_DISTRESS = auto()  # solo para nivel ELEVATED


@dataclass(frozen=True, slots=True)
class EmotionalSample:
    vector: EmotionalVector
    at: datetime


@dataclass(frozen=True, slots=True)
class CrisisInput:
    transcript: str | None
    emotion_history: tuple[EmotionalSample, ...]
    panic_button: PanicSource | None
    last_high_distress_at: datetime | None
    last_interaction_at: datetime | None
    now: datetime


@dataclass(frozen=True, slots=True)
class CrisisSignal:
    level: CrisisLevel
    reasons: tuple[CrisisReason, ...]
    detected_at: datetime

    @property
    def should_bypass_llm(self) -> bool:
        return self.level is CrisisLevel.CRISIS
