"""Tipos del módulo sync.

`SyncEventKind` es una **allow-list** de eventos que pueden viajar a
Firebase. Cualquier kind nuevo debe estar pensado a nivel de privacidad
y agregarse explícitamente — el test `test_sync_event_kind_only_includes_non_sensitive_events`
falla si alguien introduce un kind sensible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Union

PrimitiveValue = Union[str, int, float, bool, None]


class SyncEventKind(Enum):
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_CREATED_FROM_VOICE = "TASK_CREATED_FROM_VOICE"
    PANIC_BUTTON = "PANIC_BUTTON"
    ACHIEVEMENT_EARNED = "ACHIEVEMENT_EARNED"
    LEVEL_UP = "LEVEL_UP"
    DEVICE_HEARTBEAT = "DEVICE_HEARTBEAT"


@dataclass(frozen=True, slots=True)
class SyncEvent:
    id: str
    kind: SyncEventKind
    occurred_at: datetime
    payload: Mapping[str, PrimitiveValue]
