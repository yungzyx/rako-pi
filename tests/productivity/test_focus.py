from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.types import TaskStatus
from productivity.focus import (
    create_focus_task,
    first_step_suggestion,
    parse_focus_intent,
    start_focus_session,
)


def test_parse_focus_intent_detects_pomodoro_duration_and_title() -> None:
    intent = parse_focus_intent("Oye Rako, voy a empezar con estudiar cálculo por 25 minutos")

    assert intent.should_start is True
    assert intent.minutes == 25
    assert intent.task_title == "cálculo"


def test_parse_focus_intent_defaults_to_25_minutes() -> None:
    intent = parse_focus_intent("Voy a empezar a estudiar")

    assert intent.should_start is True
    assert intent.minutes == 25


def test_parse_focus_intent_ignores_unrelated_text() -> None:
    intent = parse_focus_intent("cómo estuvo mi día")

    assert intent.should_start is False
    assert intent.task_title is None


def test_create_focus_task_marks_in_progress() -> None:
    now = datetime(2026, 5, 10, 17, 0, tzinfo=UTC)

    task = create_focus_task("leer papers", now)

    assert task.title == "leer papers"
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.created_at == now


def test_start_focus_session_tracks_remaining_time() -> None:
    now = datetime(2026, 5, 10, 17, 0, tzinfo=UTC)
    task = create_focus_task("leer papers", now)

    session = start_focus_session(task, now, minutes=25)

    assert session.task_id == task.id
    assert session.ends_at == now + timedelta(minutes=25)
    assert session.remaining_at(now + timedelta(minutes=10)) == timedelta(minutes=15)
    assert session.remaining_at(now + timedelta(minutes=30)) == timedelta()


def test_first_step_suggestion_is_small_and_actionable() -> None:
    suggestion = first_step_suggestion("estudiar cálculo")

    assert "cinco minutos" in suggestion
    assert "estudiar cálculo" in suggestion
