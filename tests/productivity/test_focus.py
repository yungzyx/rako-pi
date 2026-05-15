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


def test_parse_focus_intent_understands_natural_activity_duration() -> None:
    intent = parse_focus_intent("Rako, voy a estudiar cálculo 30 minutos")

    assert intent.should_start is True
    assert intent.minutes == 30
    assert intent.duration_was_explicit is True
    assert intent.task_title == "estudiar cálculo"


def test_parse_focus_intent_understands_need_to_activity_duration() -> None:
    intent = parse_focus_intent("necesito leer papers por 45 minutos")

    assert intent.should_start is True
    assert intent.minutes == 45
    assert intent.task_title == "leer papers"


def test_parse_focus_intent_strips_rako_or_raco_invocation_from_title() -> None:
    intent = parse_focus_intent("Raco, hazme un pomodoro de 10 minutos para estudiar")

    assert intent.should_start is True
    assert intent.minutes == 10
    assert intent.task_title == "estudiar"


def test_parse_focus_intent_handles_oye_raco_prefix() -> None:
    intent = parse_focus_intent("Oye Raco hazme un pomodoro de 15 minutos para cálculo")

    assert intent.task_title == "cálculo"


def test_parse_focus_intent_handles_whisper_rako_mishearing() -> None:
    intent = parse_focus_intent("Rackle, hazme un pomodoro de 10 minutos para estudiar")

    assert intent.task_title == "estudiar"


def test_parse_focus_intent_ignores_low_value_task_title() -> None:
    intent = parse_focus_intent("Rackle, hazme un pomodoro de 10 minutos para que")

    assert intent.should_start is True
    assert intent.task_title is None


def test_parse_focus_intent_detects_activity_without_duration() -> None:
    intent = parse_focus_intent("Rako, voy a limpiar mi pieza")

    assert intent.should_start is True
    assert intent.duration_was_explicit is False
    assert intent.task_title == "mi pieza"


def test_parse_focus_intent_accepts_general_activities() -> None:
    intent = parse_focus_intent("quiero programar el proyecto 40 minutos")

    assert intent.should_start is True
    assert intent.duration_was_explicit is True
    assert intent.task_title == "proyecto"


def test_parse_focus_intent_ignores_unrelated_text() -> None:
    intent = parse_focus_intent("cómo estuvo mi día")

    assert intent.should_start is False
    assert intent.task_title is None


def test_parse_focus_intent_never_turns_crisis_language_into_timer() -> None:
    intent = parse_focus_intent("Me quiero matar.")

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
