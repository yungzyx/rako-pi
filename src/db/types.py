"""Entidades del estado local.

Inmutables (`frozen=True`). Los repositorios devuelven instancias nuevas
en cada operación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CrisisJournalEntry:
    id: str
    detected_at: datetime
    level: str
    reasons: tuple[str, ...]
    response_id: str | None
    contact_notified: bool
    recorded_at: datetime
