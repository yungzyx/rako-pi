from __future__ import annotations

from datetime import UTC, datetime

import pytest

from db.database import Database
from db.types import TaskStatus
from productivity.runtime import maybe_start_focus_from_transcript


@pytest.fixture
def db(db_conn) -> Database:
    return Database(db_conn)


def test_maybe_start_focus_from_transcript_creates_task_and_response(db) -> None:
    now = datetime(2026, 5, 10, 17, 30, tzinfo=UTC)

    result = maybe_start_focus_from_transcript(
        "voy a empezar con estudiar calculo por 25 minutos",
        db=db,
        now=now,
    )

    assert result is not None
    assert result.session is not None
    task = db.tasks.find_by_id(result.session.task_id)
    assert task is not None
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.title == "calculo"
    assert result.session.duration.total_seconds() == 25 * 60
    assert "bloque de foco de 25 minutos" in result.response_text
    assert "WhatsApp" not in result.response_text


def test_maybe_start_focus_from_transcript_returns_none_for_general_turn(db) -> None:
    now = datetime(2026, 5, 10, 17, 30, tzinfo=UTC)

    result = maybe_start_focus_from_transcript("hola, cómo estás", db=db, now=now)

    assert result is None
    assert db.tasks.list_pending() == []


def test_maybe_start_focus_returns_none_for_help_seeking_study_turn(db) -> None:
    now = datetime(2026, 5, 10, 17, 30, tzinfo=UTC)

    result = maybe_start_focus_from_transcript(
        "No sé cómo empezar a estudiar con una tarea.",
        db=db,
        now=now,
    )

    assert result is None
    assert db.tasks.list_pending() == []


def test_maybe_start_focus_asks_duration_when_missing(db) -> None:
    now = datetime(2026, 5, 10, 17, 30, tzinfo=UTC)

    result = maybe_start_focus_from_transcript("Rako, voy a limpiar mi pieza", db=db, now=now)

    assert result is not None
    assert result.session is None
    assert result.needs_duration is True
    assert result.suggested_title == "mi pieza"
    assert "Por cuántos minutos" in result.response_text
    assert db.tasks.list_pending() == []


def test_maybe_start_focus_mentions_whatsapp_only_when_enabled(db) -> None:
    now = datetime(2026, 5, 10, 17, 30, tzinfo=UTC)

    result = maybe_start_focus_from_transcript(
        "hazme un pomodoro de 15 minutos",
        db=db,
        now=now,
        notify_external=True,
    )

    assert result is not None
    assert result.session is not None
    assert "WhatsApp" in result.response_text
    assert "Sesión de foco" in result.session.task_title
