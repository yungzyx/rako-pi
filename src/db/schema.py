"""Esquema SQL del estado local del usuario.

DDL idempotente — `create_all(conn)` se puede invocar N veces sin
error. Sustituye un sistema de migraciones hasta que haya cambios de
esquema reales.

Tablas (ver Arquitectura §5.1):

- tasks               tareas y micro-tareas (parent_id self-referencing)
- interactions        historial de turnos (transcripción truncada)
- emotional_states    timeline de vectores emocionales
- achievements        logros y progresión
- user_config         clave/valor para settings locales
- crisis_events       journal privado de eventos de crisis
- sync_queue          eventos pendientes de sync con Firebase
"""

from __future__ import annotations

import sqlite3
from typing import Final

EXPECTED_TABLES: Final[tuple[str, ...]] = (
    "tasks",
    "interactions",
    "emotional_states",
    "achievements",
    "user_config",
    "crisis_events",
    "sync_queue",
)


_DDL: Final[tuple[str, ...]] = (
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id           TEXT PRIMARY KEY,
        title        TEXT NOT NULL,
        description  TEXT,
        parent_id    TEXT,
        status       TEXT NOT NULL CHECK (status IN ('TODO','IN_PROGRESS','DONE','CANCELLED')),
        created_at   TEXT NOT NULL,
        completed_at TEXT,
        source       TEXT NOT NULL CHECK (source IN ('VOICE','APP','PROACTIVE')),
        FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id)",
    """
    CREATE TABLE IF NOT EXISTS interactions (
        id                     TEXT PRIMARY KEY,
        timestamp              TEXT NOT NULL,
        type                   TEXT NOT NULL,
        transcription_excerpt  TEXT,
        valence                REAL,
        arousal                REAL,
        dominance              REAL,
        response_id            TEXT,
        response_text          TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_interactions_ts ON interactions(timestamp DESC)",
    """
    CREATE TABLE IF NOT EXISTS emotional_states (
        id            TEXT PRIMARY KEY,
        at            TEXT NOT NULL,
        valence       REAL NOT NULL,
        arousal       REAL NOT NULL,
        dominance     REAL NOT NULL,
        trigger_event TEXT,
        confidence    REAL NOT NULL DEFAULT 0.0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emostates_at ON emotional_states(at DESC)",
    """
    CREATE TABLE IF NOT EXISTS achievements (
        id                  TEXT PRIMARY KEY,
        type                TEXT NOT NULL,
        earned_at           TEXT NOT NULL,
        robot_level_after   INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_config (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS crisis_events (
        id                TEXT PRIMARY KEY,
        detected_at       TEXT NOT NULL,
        level             TEXT NOT NULL,
        reasons           TEXT NOT NULL,            -- JSON array de CrisisReason names
        response_id       TEXT,
        contact_notified  INTEGER NOT NULL DEFAULT 0,
        recorded_at       TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_crisis_recorded ON crisis_events(recorded_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS sync_queue (
        id            TEXT PRIMARY KEY,
        created_at    TEXT NOT NULL,
        event_type    TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        attempts      INTEGER NOT NULL DEFAULT 0,
        last_error    TEXT
    )
    """,
)


def create_all(conn: sqlite3.Connection) -> None:
    """Aplica todo el DDL. Idempotente."""
    with conn:
        for stmt in _DDL:
            conn.execute(stmt)
