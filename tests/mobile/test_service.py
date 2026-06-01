from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database
from db.types import TaskStatus
from mobile.service import MobileService, focus_start_to_dict, status_to_dict


def test_status_is_ready_without_active_focus(db_conn) -> None:
    service = MobileService(Database(db_conn))

    status = service.status(datetime(2026, 6, 1, 15, 0, tzinfo=UTC))

    assert status_to_dict(status)["state"] == "ready"
    assert status.active_focus is None


def test_start_focus_stores_active_focus_for_mobile_status(db_conn) -> None:
    db = Database(db_conn)
    service = MobileService(db)
    now = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)

    result = service.start_focus(title="cálculo", minutes=30, now=now)
    status = service.status(now + timedelta(minutes=5))

    assert focus_start_to_dict(result)["title"] == "cálculo"
    assert result.minutes == 30
    assert "30 minutos para cálculo" in result.response_text
    assert status.state == "focus"
    assert status.active_focus is not None
    assert status.active_focus["title"] == "cálculo"
    assert status.active_focus["remaining_seconds"] == 25 * 60


def test_status_completes_expired_focus(db_conn) -> None:
    db = Database(db_conn)
    service = MobileService(db)
    now = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)

    result = service.start_focus(title="leer", minutes=1, now=now)
    status = service.status(now + timedelta(minutes=2))
    task = db.tasks.find_by_id(result.task_id)

    assert status.state == "ready"
    assert status.active_focus is None
    assert task is not None
    assert task.status is TaskStatus.DONE


def test_cancel_focus_clears_state_and_marks_task_cancelled(db_conn) -> None:
    db = Database(db_conn)
    service = MobileService(db)
    now = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)

    result = service.start_focus(title="programar", minutes=20, now=now)
    cancelled = service.cancel_focus(now=now + timedelta(minutes=3))
    status = service.status(now + timedelta(minutes=3))
    task = db.tasks.find_by_id(result.task_id)

    assert cancelled is True
    assert status.state == "ready"
    assert task is not None
    assert task.status is TaskStatus.CANCELLED
