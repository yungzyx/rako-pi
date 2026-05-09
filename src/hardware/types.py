"""Tipos del módulo hardware."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LEDState(Enum):
    OFF = "OFF"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    PRESENT = "PRESENT"  # estado del protocolo de crisis
    ALERT_SOFT = "ALERT_SOFT"  # nudge proactivo, pulso lento


class HardwareEventKind(Enum):
    PIR_MOTION = "PIR_MOTION"
    TOUCH = "TOUCH"
    WAKE_WORD = "WAKE_WORD"
    BUTTON_PANIC = "BUTTON_PANIC"
    BUTTON_EMERGENCY = "BUTTON_EMERGENCY"


@dataclass(frozen=True, slots=True)
class HardwareEvent:
    kind: HardwareEventKind
    at: datetime
