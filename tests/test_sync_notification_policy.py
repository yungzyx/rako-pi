from __future__ import annotations

from datetime import UTC, datetime

from productivity.focus import create_focus_task, start_focus_session
from sync.notification_policy import (
    ExternalChannel,
    ExternalNotificationKind,
    focus_completed_notification,
    focus_started_notification,
)


def test_focus_started_notification_hides_task_title_by_default() -> None:
    now = datetime(2026, 5, 10, 17, 0, tzinfo=UTC)
    task = create_focus_task("leer papers secretos", now)
    session = start_focus_session(task, now, minutes=25)

    notification = focus_started_notification(session)

    assert notification.channel is ExternalChannel.WHATSAPP
    assert notification.kind is ExternalNotificationKind.FOCUS_STARTED
    assert "25 min" in notification.text
    assert "leer papers secretos" not in notification.text
    assert notification.metadata["task_id"] == task.id


def test_focus_started_notification_can_include_title_when_opted_in() -> None:
    now = datetime(2026, 5, 10, 17, 0, tzinfo=UTC)
    task = create_focus_task("leer papers", now)
    session = start_focus_session(task, now, minutes=15)

    notification = focus_started_notification(session, include_task_title=True)

    assert "leer papers" in notification.text


def test_focus_completed_notification_is_generic() -> None:
    now = datetime(2026, 5, 10, 17, 0, tzinfo=UTC)
    task = create_focus_task("leer papers", now)
    session = start_focus_session(task, now, minutes=15)

    notification = focus_completed_notification(session)

    assert notification.kind is ExternalNotificationKind.FOCUS_COMPLETED
    assert notification.text == "Rako terminó una sesión de foco."
