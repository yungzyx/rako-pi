"""Privacy policy for external notifications such as WhatsApp.

This module decides what is safe to send outside the Pi. It never sends by
itself; adapters can consume `ExternalNotification` later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from productivity.focus import FocusSession


class ExternalChannel(Enum):
    WHATSAPP = "WHATSAPP"
    APP_PUSH = "APP_PUSH"


class ExternalNotificationKind(Enum):
    FOCUS_STARTED = "FOCUS_STARTED"
    FOCUS_COMPLETED = "FOCUS_COMPLETED"
    TASK_CREATED = "TASK_CREATED"


@dataclass(frozen=True, slots=True)
class ExternalNotification:
    channel: ExternalChannel
    kind: ExternalNotificationKind
    text: str
    metadata: dict[str, str]


def focus_started_notification(
    session: FocusSession,
    *,
    channel: ExternalChannel = ExternalChannel.WHATSAPP,
    include_task_title: bool = False,
) -> ExternalNotification:
    """Build a privacy-preserving focus-start notification.

    By default it does not include the task title because WhatsApp is external.
    The user can opt in later to include task titles.
    """
    minutes = int(session.duration.total_seconds() // 60)
    if include_task_title:
        text = f"Rako inició una sesión de foco de {minutes} min: {session.task_title}."
    else:
        text = f"Rako inició una sesión de foco de {minutes} min."
    return ExternalNotification(
        channel=channel,
        kind=ExternalNotificationKind.FOCUS_STARTED,
        text=text,
        metadata={"focus_session_id": session.id, "task_id": session.task_id},
    )


def focus_completed_notification(
    session: FocusSession,
    *,
    channel: ExternalChannel = ExternalChannel.WHATSAPP,
) -> ExternalNotification:
    return ExternalNotification(
        channel=channel,
        kind=ExternalNotificationKind.FOCUS_COMPLETED,
        text="Rako terminó una sesión de foco.",
        metadata={"focus_session_id": session.id, "task_id": session.task_id},
    )
