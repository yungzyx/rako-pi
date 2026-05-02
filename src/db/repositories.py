"""Repositorios sobre el estado local.

Cada repo encapsula una tabla. Operaciones inmutables: cada update
devuelve una entidad nueva. Toda escritura usa parametrized queries.

Los repos NO loggean valores sensibles (transcripciones, claves, vectores
emocionales crudos) — solo IDs cuando hace falta diagnóstico.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Final

from db.types import (
    Achievement,
    EmotionalStateRecord,
    Interaction,
    InteractionType,
    Task,
    TaskSource,
    TaskStatus,
)
from emotion.types import EmotionalVector
from safety.types import EmotionalSample

# Privacidad: la transcripción nunca se persiste completa. Es un
# "excerpt" — el detector ya tomó su decisión sobre el texto entero,
# aquí solo guardamos un fragmento para que el usuario reconozca el
# turno al revisar el historial.
TRANSCRIPT_MAX_LEN: Final[int] = 200


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, task: Task) -> Task:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO tasks
                    (id, title, description, parent_id, status,
                     created_at, completed_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.title,
                    task.description,
                    task.parent_id,
                    task.status.value,
                    task.created_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.source.value,
                ),
            )
        return task

    def find_by_id(self, id: str) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_by_status(self, status: TaskStatus) -> list[Task]:
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
            (status.value,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def list_pending(self) -> list[Task]:
        rows = self._conn.execute(
            """
            SELECT * FROM tasks
            WHERE status IN ('TODO', 'IN_PROGRESS')
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def list_children(self, parent_id: str) -> list[Task]:
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at",
            (parent_id,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def update_status(
        self,
        id: str,
        status: TaskStatus,
        completed_at: datetime | None = None,
    ) -> Task:
        existing = self.find_by_id(id)
        if existing is None:
            raise KeyError(f"task not found: {id}")

        completed_iso = completed_at.isoformat() if completed_at else None
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
                (status.value, completed_iso, id),
            )
        # Devuelve una nueva instancia inmutable.
        return Task(
            id=existing.id,
            title=existing.title,
            description=existing.description,
            parent_id=existing.parent_id,
            status=status,
            created_at=existing.created_at,
            completed_at=completed_at,
            source=existing.source,
        )

    def delete(self, id: str) -> bool:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
        return cursor.rowcount > 0

    def purge_all(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM tasks")
        return cursor.rowcount

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            parent_id=row["parent_id"],
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            source=TaskSource(row["source"]),
        )


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


class InteractionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(self, interaction: Interaction) -> Interaction:
        excerpt = _truncate(interaction.transcription_excerpt, TRANSCRIPT_MAX_LEN)
        emotion = interaction.emotion
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO interactions
                    (id, timestamp, type, transcription_excerpt,
                     valence, arousal, dominance,
                     response_id, response_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction.id,
                    interaction.timestamp.isoformat(),
                    interaction.type.value,
                    excerpt,
                    emotion.valence if emotion else None,
                    emotion.arousal if emotion else None,
                    emotion.dominance if emotion else None,
                    interaction.response_id,
                    interaction.response_text,
                ),
            )
        # Devuelve la versión efectivamente persistida (con excerpt
        # truncado, no el original que pueda haber traído más texto).
        return Interaction(
            id=interaction.id,
            timestamp=interaction.timestamp,
            type=interaction.type,
            transcription_excerpt=excerpt,
            emotion=interaction.emotion,
            response_id=interaction.response_id,
            response_text=interaction.response_text,
        )

    def list_recent(self, limit: int = 50) -> list[Interaction]:
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        rows = self._conn.execute(
            """
            SELECT * FROM interactions
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_interaction(r) for r in rows]

    def purge_all(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM interactions")
        return cursor.rowcount

    @staticmethod
    def _row_to_interaction(row: sqlite3.Row) -> Interaction:
        emotion: EmotionalVector | None = None
        if row["valence"] is not None:
            emotion = EmotionalVector(
                valence=row["valence"],
                arousal=row["arousal"],
                dominance=row["dominance"],
            )
        return Interaction(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            type=InteractionType(row["type"]),
            transcription_excerpt=row["transcription_excerpt"],
            emotion=emotion,
            response_id=row["response_id"],
            response_text=row["response_text"],
        )


# ---------------------------------------------------------------------------
# Emotional states
# ---------------------------------------------------------------------------


class EmotionalStateRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(self, record: EmotionalStateRecord) -> EmotionalStateRecord:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO emotional_states
                    (id, at, valence, arousal, dominance, trigger_event, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.at.isoformat(),
                    record.vector.valence,
                    record.vector.arousal,
                    record.vector.dominance,
                    record.trigger_event,
                    record.confidence,
                ),
            )
        return record

    def list_in_window(self, end: datetime, lookback: timedelta) -> list[EmotionalStateRecord]:
        if lookback.total_seconds() < 0:
            raise ValueError(f"lookback must be non-negative, got {lookback}")
        start = end - lookback
        rows = self._conn.execute(
            """
            SELECT * FROM emotional_states
            WHERE at >= ? AND at <= ?
            ORDER BY at ASC
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_samples_in_window(
        self, end: datetime, lookback: timedelta
    ) -> tuple[EmotionalSample, ...]:
        return tuple(r.to_sample() for r in self.list_in_window(end, lookback))

    def purge_all(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM emotional_states")
        return cursor.rowcount

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> EmotionalStateRecord:
        return EmotionalStateRecord(
            id=row["id"],
            at=datetime.fromisoformat(row["at"]),
            vector=EmotionalVector(
                valence=row["valence"],
                arousal=row["arousal"],
                dominance=row["dominance"],
            ),
            trigger_event=row["trigger_event"],
            confidence=row["confidence"],
        )


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------


class AchievementRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record(self, achievement: Achievement) -> Achievement:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO achievements (id, type, earned_at, robot_level_after)
                VALUES (?, ?, ?, ?)
                """,
                (
                    achievement.id,
                    achievement.type,
                    achievement.earned_at.isoformat(),
                    achievement.robot_level_after,
                ),
            )
        return achievement

    def list_all(self) -> list[Achievement]:
        rows = self._conn.execute("SELECT * FROM achievements ORDER BY earned_at DESC").fetchall()
        return [
            Achievement(
                id=r["id"],
                type=r["type"],
                earned_at=datetime.fromisoformat(r["earned_at"]),
                robot_level_after=r["robot_level_after"],
            )
            for r in rows
        ]

    def purge_all(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM achievements")
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Config (key/value)
# ---------------------------------------------------------------------------


class ConfigRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM user_config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        now_iso = datetime.now().astimezone().isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO user_config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                               updated_at = excluded.updated_at
                """,
                (key, value, now_iso),
            )

    def delete(self, key: str) -> bool:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM user_config WHERE key = ?", (key,))
        return cursor.rowcount > 0

    def get_all(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM user_config").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def purge_all(self) -> int:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM user_config")
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str | None, max_len: int) -> str | None:
    if text is None:
        return None
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
