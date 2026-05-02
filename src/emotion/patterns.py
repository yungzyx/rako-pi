"""Análisis de patrones de comportamiento → señal proactiva.

No depende de modelos pesados. Combina señales no-acústicas para que
el orquestador decida si iniciar un turno (intervención breve, voz
baja). El umbral conservador prefiere NO molestar antes que insistir.

Ver Arquitectura §4.2 (Detección proactiva de bloqueo).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, IntEnum

# ---------------------------------------------------------------------------
# Umbrales (constantes nombradas)
# ---------------------------------------------------------------------------

_MILD_INACTIVITY = timedelta(hours=4)
_MODERATE_INACTIVITY = timedelta(hours=12)
_PENDING_LOAD_TRIGGER = 10
_LATE_NIGHT_START_HOUR = 1
_LATE_NIGHT_END_HOUR = 5


class BlockLevel(IntEnum):
    NONE = 0
    MILD = 1
    MODERATE = 2


class BlockReason(Enum):
    PROLONGED_INACTIVITY = "PROLONGED_INACTIVITY"
    HIGH_PENDING_LOAD = "HIGH_PENDING_LOAD"
    LATE_NIGHT = "LATE_NIGHT"


@dataclass(frozen=True, slots=True)
class PatternInput:
    last_interaction_at: datetime | None
    pending_task_count: int
    do_not_disturb: bool
    now: datetime


@dataclass(frozen=True, slots=True)
class BlockSignal:
    level: BlockLevel
    reasons: tuple[BlockReason, ...]
    detected_at: datetime


def analyze_patterns(input: PatternInput) -> BlockSignal:
    """Devuelve una señal de bloqueo a partir de patrones de actividad."""
    if input.do_not_disturb:
        return BlockSignal(BlockLevel.NONE, (), input.now)

    if input.last_interaction_at is None:
        return BlockSignal(BlockLevel.NONE, (), input.now)

    reasons: list[BlockReason] = []
    level = BlockLevel.NONE

    inactivity = input.now - input.last_interaction_at
    if inactivity >= _MODERATE_INACTIVITY:
        reasons.append(BlockReason.PROLONGED_INACTIVITY)
        level = max(level, BlockLevel.MODERATE)
    elif inactivity >= _MILD_INACTIVITY:
        reasons.append(BlockReason.PROLONGED_INACTIVITY)
        level = max(level, BlockLevel.MILD)

    if input.pending_task_count >= _PENDING_LOAD_TRIGGER:
        reasons.append(BlockReason.HIGH_PENDING_LOAD)
        level = max(level, BlockLevel.MILD)

    if (
        _LATE_NIGHT_START_HOUR <= input.now.hour < _LATE_NIGHT_END_HOUR
        and inactivity >= _MILD_INACTIVITY
    ):
        reasons.append(BlockReason.LATE_NIGHT)
        level = max(level, BlockLevel.MILD)

    return BlockSignal(level=level, reasons=tuple(reasons), detected_at=input.now)
