"""Facade `Database` — compone los repos sobre una conexión.

Punto de entrada habitual:

    db = Database.open(path, key)         # cifra si key != None
    db.tasks.create(...)
    db.crisis_journal.record(...)
    db.purge_all_user_data()              # borrado total (privacidad)
    db.close()
"""

from __future__ import annotations

import sqlite3
from typing import Self

from db.connection import open_connection
from db.connection import require_encrypted as _require_encrypted
from db.journal import CrisisJournal
from db.repositories import (
    AchievementRepository,
    ConfigRepository,
    EmotionalStateRepository,
    InteractionRepository,
    TaskRepository,
)
from db.schema import create_all


class Database:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._closed = False
        self.tasks = TaskRepository(conn)
        self.interactions = InteractionRepository(conn)
        self.emotional_states = EmotionalStateRepository(conn)
        self.achievements = AchievementRepository(conn)
        self.config = ConfigRepository(conn)
        self.crisis_journal = CrisisJournal(conn)

    @classmethod
    def open(cls, path: str, key: str | None = None) -> Self:
        """Abre o crea la base, aplica el schema, y devuelve un Database."""
        conn = open_connection(path, key)
        create_all(conn)
        return cls(conn)

    def require_encrypted(self) -> None:
        """Aborta (`EncryptionRequiredError`) si la conexión no está cifrada.

        Llamar antes de aceptar tráfico productivo (CLAUDE.md §4.1.6).
        """
        _require_encrypted(self._conn)

    def purge_all_user_data(self) -> None:
        """Borra TODO el historial e identidad del usuario.

        Cumple §6 del documento de arquitectura: "El usuario puede borrar
        todo su historial desde la app, con efecto inmediato en la Pi."
        """
        self.tasks.purge_all()
        self.interactions.purge_all()
        self.emotional_states.purge_all()
        self.achievements.purge_all()
        self.config.purge_all()
        self.crisis_journal.purge()

    def close(self) -> None:
        if self._closed:
            return
        self._conn.close()
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
