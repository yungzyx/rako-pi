"""CrisisJournal — registro privado de eventos de crisis.

Implementa el Protocol `_Journal` que `safety.protocol` consume. Los
rows nunca salen de la Pi y sobreviven a fallos downstream (la voz
puede no sonar, la red puede caer, pero el evento queda anotado).

No persiste audio ni transcripciones — solo metadatos.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Final

from safety.types import CrisisLevel, CrisisSignal

from db.types import CrisisJournalEntry

_UTC = timezone.utc
_DEFAULT_LIMIT: Final[int] = 50


class CrisisJournal:
    """Repositorio del journal de crisis."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record(
        self,
        signal: CrisisSignal,
        *,
        response_id: str | None = None,
        contact_notified: bool = False,
    ) -> None:
        """Persiste el signal. Solo acepta nivel CRISIS."""
        if signal.level is not CrisisLevel.CRISIS:
            raise ValueError(
                f"CrisisJournal only records CRISIS signals, got {signal.level.name}"
            )

        reasons_json = json.dumps([r.name for r in signal.reasons])
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO crisis_events
                    (id, detected_at, level, reasons, response_id,
                     contact_notified, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    signal.detected_at.isoformat(),
                    signal.level.name,
                    reasons_json,
                    response_id,
                    1 if contact_notified else 0,
                    datetime.now(_UTC).isoformat(),
                ),
            )

    def list_recent(self, limit: int = _DEFAULT_LIMIT) -> list[CrisisJournalEntry]:
        """Devuelve los `limit` eventos más recientes (más nuevos primero)."""
        rows = self._conn.execute(
            """
            SELECT id, detected_at, level, reasons, response_id,
                   contact_notified, recorded_at
            FROM crisis_events
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def purge(self) -> int:
        """Borra todos los eventos. Devuelve cuántos rows se eliminaron."""
        with self._conn:
            cursor = self._conn.execute("DELETE FROM crisis_events")
            return cursor.rowcount

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> CrisisJournalEntry:
        return CrisisJournalEntry(
            id=row["id"],
            detected_at=datetime.fromisoformat(row["detected_at"]),
            level=row["level"],
            reasons=tuple(json.loads(row["reasons"])),
            response_id=row["response_id"],
            contact_notified=bool(row["contact_notified"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )
