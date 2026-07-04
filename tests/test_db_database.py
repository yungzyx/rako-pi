"""Tests del facade Database — composición de repos + privacy.purge."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from db.database import Database
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
from safety.types import CrisisLevel, CrisisReason, CrisisSignal

UTC = UTC


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _seed(db: Database) -> None:
    db.tasks.create(
        Task(
            id="t",
            title="x",
            description=None,
            parent_id=None,
            status=TaskStatus.TODO,
            created_at=_now(),
            completed_at=None,
            source=TaskSource.VOICE,
        )
    )
    db.interactions.append(
        Interaction(
            id="i",
            timestamp=_now(),
            type=InteractionType.USER_VOICE,
            transcription_excerpt="x",
            emotion=None,
            response_id=None,
            response_text=None,
        )
    )
    db.emotional_states.append(
        EmotionalStateRecord(
            id="e",
            at=_now(),
            vector=EmotionalVector(0.0, 0.5, 0.5),
            trigger_event=None,
            confidence=0.9,
        )
    )
    db.achievements.record(Achievement(id="a", type="x", earned_at=_now(), robot_level_after=1))
    db.config.set("theme", "dark")
    db.crisis_journal.record(
        CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.PANIC_BUTTON_PHYSICAL,),
            detected_at=_now(),
        )
    )


def test_database_open_creates_schema(tmp_path: Path) -> None:
    db = Database.open(str(tmp_path / "test.db"))
    try:
        _seed(db)
    finally:
        db.close()


def test_purge_all_user_data_clears_everything(tmp_path: Path) -> None:
    db = Database.open(str(tmp_path / "test.db"))
    _seed(db)

    db.purge_all_user_data()

    assert db.tasks.list_pending() == []
    assert db.interactions.list_recent() == []
    assert db.config.get_all() == {}
    assert db.achievements.list_all() == []
    assert db.crisis_journal.list_recent() == []
    db.close()


def test_database_require_encrypted_delegates_to_connection_boundary(tmp_path: Path) -> None:
    from db.connection import EncryptionRequiredError

    # Sin SQLCipher instalado (como en este sandbox de dev/CI), abrir sin
    # key nunca queda cifrado — `require_encrypted` debe abortar.
    db = Database.open(str(tmp_path / "test.db"))
    try:
        with pytest.raises(EncryptionRequiredError):
            db.require_encrypted()
    finally:
        db.close()


def test_database_close_is_idempotent(tmp_path: Path) -> None:
    db = Database.open(str(tmp_path / "test.db"))

    db.close()
    db.close()  # debe poder cerrarse dos veces sin error


def test_database_works_as_context_manager(tmp_path: Path) -> None:
    path = str(tmp_path / "test.db")

    with Database.open(path) as db:
        _seed(db)

    # Tras salir del contexto, la conexión queda cerrada y reabrir la
    # base preserva los datos.
    with Database.open(path) as db:
        assert db.tasks.find_by_id("t") is not None
