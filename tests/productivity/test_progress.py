from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database
from db.types import TaskSource, TaskStatus
from productivity.focus import create_focus_task
from productivity.progress import (
    build_external_progress_message,
    build_progress_summary,
    progress_summary_to_dict,
)


def test_progress_summary_counts_today_completed_and_pending(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 10, 18, 0, tzinfo=UTC)
    done = db.tasks.create(create_focus_task("cálculo", now - timedelta(hours=2)))
    pending = db.tasks.create(create_focus_task("leer papers", now - timedelta(minutes=20)))
    db.tasks.update_status(done.id, TaskStatus.DONE, completed_at=now - timedelta(hours=1))

    summary = build_progress_summary(db, now=now, period="today")

    assert summary.tasks_created == 2
    assert summary.tasks_completed == 1
    assert summary.pending_task_count == 1
    assert summary.active_task_count == 1
    assert summary.completion_titles == ("cálculo",)
    assert summary.next_task_title == pending.title
    assert "Hoy completaste 1 tarea" in summary.message


def test_progress_summary_week_includes_previous_days(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 10, 18, 0, tzinfo=UTC)
    monday = datetime(2026, 6, 8, 10, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("programar", monday, source=TaskSource.APP))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=monday + timedelta(hours=1))

    today = build_progress_summary(db, now=now, period="today")
    week = build_progress_summary(db, now=now, period="week")

    assert today.tasks_completed == 0
    assert week.tasks_completed == 1
    assert week.period == "week"


def test_progress_summary_to_dict_is_api_friendly(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 10, 18, 0, tzinfo=UTC)

    payload = progress_summary_to_dict(build_progress_summary(db, now=now))

    assert payload["period"] == "today"
    assert payload["tasks_completed"] == 0
    assert isinstance(payload["message"], str)


def test_external_progress_message_does_not_include_task_titles(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 10, 18, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("tarea privada", now - timedelta(hours=1)))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=now)

    message = build_external_progress_message(build_progress_summary(db, now=now))

    assert "completaste 1 tarea" in message
    assert "tarea privada" not in message
