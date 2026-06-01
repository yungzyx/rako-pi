"""Runtime helpers for focus/task handling.

This module bridges pure focus-domain logic with the local database and safe
notification events. It is still synchronous and lightweight; countdown service
integration can be layered on top later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from db.database import Database
from productivity.focus import (
    FocusSession,
    create_focus_task,
    first_step_suggestion,
    parse_focus_intent,
    start_focus_session,
)
from sync.notification_policy import ExternalNotification, focus_started_notification


@dataclass(frozen=True, slots=True)
class FocusStartResult:
    session: FocusSession | None
    response_text: str
    notification: ExternalNotification | None
    needs_duration: bool = False
    suggested_title: str | None = None


def maybe_start_focus_from_transcript(
    transcript: str,
    *,
    db: Database,
    now: datetime,
    notify_external: bool = False,
) -> FocusStartResult | None:
    intent = parse_focus_intent(transcript)
    if not intent.should_start:
        return None

    if not intent.duration_was_explicit:
        title = intent.task_title or "esa actividad"
        return FocusStartResult(
            session=None,
            response_text=(
                f"Dale. ¿Por cuántos minutos quieres hacer {title}? "
                "Si quieres, te recomiendo 25 minutos para partir."
            ),
            notification=None,
            needs_duration=True,
            suggested_title=title,
        )

    title = intent.task_title or "Sesión de foco"
    task = db.tasks.create(create_focus_task(title, now))
    session = start_focus_session(task, now, minutes=intent.minutes)
    notification = focus_started_notification(session)
    response = _build_focus_response(session=session, notify_external=notify_external)
    return FocusStartResult(session=session, response_text=response, notification=notification)


def _build_focus_response(*, session: FocusSession, notify_external: bool) -> str:
    minutes = int(session.duration.total_seconds() // 60)
    suggestion = first_step_suggestion(session.task_title)
    notification_text = " Te avisaré por WhatsApp con un resumen seguro." if notify_external else ""
    title = session.task_title.strip()
    if title.lower() == "sesión de foco":
        intro = f"Dale, partimos con {minutes} minutos."
    else:
        intro = f"Dale, partimos: {minutes} minutos para {title}."
    return f"{intro} {suggestion}{notification_text}"
