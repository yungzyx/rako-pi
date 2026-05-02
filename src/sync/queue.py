"""Cola persistente de eventos pendientes de sync.

Usa la tabla `sync_queue` ya creada en `db.schema`. Cada evento se
sanitiza al encolar (defense-in-depth: incluso si un módulo upstream
deja pasar PII, el sanitizer la limpia antes de tocar disco).

Eventos que fallan demasiadas veces (`max_attempts`) se dead-lettearn:
no se eliminan de la tabla pero `list_pending` ya no los devuelve, así
no se reintenta indefinidamente y el operador puede inspeccionarlos.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sync.sanitizer import sanitize_payload
from sync.types import SyncEvent, SyncEventKind

_DEFAULT_LIMIT: Final[int] = 100
_DEFAULT_MAX_ATTEMPTS: Final[int] = 5


@dataclass(frozen=True, slots=True)
class QueuedSyncEvent:
    event: SyncEvent
    attempts: int
    last_error: str | None
    created_at: datetime


class SyncQueue:
    def __init__(
        self,
        conn: sqlite3.Connection,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._conn = conn
        self._max_attempts = max_attempts

    def enqueue(self, event: SyncEvent) -> None:
        clean_payload = sanitize_payload(event.payload)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sync_queue
                    (id, created_at, event_type, payload_json, attempts, last_error)
                VALUES (?, ?, ?, ?, 0, NULL)
                """,
                (
                    event.id,
                    event.occurred_at.isoformat(),
                    event.kind.name,
                    json.dumps({"_kind_value": event.kind.value, **clean_payload}),
                ),
            )

    def list_pending(self, limit: int = _DEFAULT_LIMIT) -> list[QueuedSyncEvent]:
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        rows = self._conn.execute(
            """
            SELECT id, created_at, event_type, payload_json, attempts, last_error
            FROM sync_queue
            WHERE attempts < ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (self._max_attempts, limit),
        ).fetchall()
        return [self._row_to_queued(row) for row in rows]

    def mark_succeeded(self, queued: QueuedSyncEvent) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM sync_queue WHERE id = ?", (queued.event.id,))

    def mark_failed(self, queued: QueuedSyncEvent, *, error: str) -> None:
        with self._conn:
            self._conn.execute(
                """
                UPDATE sync_queue
                SET attempts = attempts + 1,
                    last_error = ?
                WHERE id = ?
                """,
                (error, queued.event.id),
            )

    def purge_all(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM sync_queue")
        return cursor.rowcount

    @staticmethod
    def _row_to_queued(row: sqlite3.Row) -> QueuedSyncEvent:
        payload = json.loads(row["payload_json"])
        payload.pop("_kind_value", None)
        event = SyncEvent(
            id=row["id"],
            kind=SyncEventKind[row["event_type"]],
            occurred_at=datetime.fromisoformat(row["created_at"]),
            payload=payload,
        )
        return QueuedSyncEvent(
            event=event,
            attempts=row["attempts"],
            last_error=row["last_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
