"""Pure service layer for the future Rako mobile app.

The service intentionally has no FastAPI dependency. HTTP, Flutter, or local
CLI adapters can call this layer and get the same behavior.
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from db.database import Database
from db.types import TaskSource, TaskStatus
from productivity.focus import FocusSession, create_focus_task, start_focus_session
from productivity.runtime import _build_focus_response

_ACTIVE_FOCUS_KEY = "mobile.active_focus"


@dataclass(frozen=True, slots=True)
class MobileStatus:
    state: str
    active_focus: dict[str, Any] | None
    pending_task_count: int


@dataclass(frozen=True, slots=True)
class MobileFocusStart:
    task_id: str
    focus_session_id: str
    title: str
    minutes: int
    started_at: str
    ends_at: str
    response_text: str


class MobileService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def status(self, now: datetime | None = None) -> MobileStatus:
        now = _ensure_aware(now or datetime.now(UTC))
        active_focus = self._active_focus(now)
        return MobileStatus(
            state="focus" if active_focus is not None else "ready",
            active_focus=active_focus,
            pending_task_count=len(self._db.tasks.list_pending()),
        )

    def start_focus(self, *, title: str | None, minutes: int, now: datetime | None = None) -> MobileFocusStart:
        now = _ensure_aware(now or datetime.now(UTC))
        clean_title = _clean_title(title)
        task = self._db.tasks.create(
            create_focus_task(clean_title, now, source=TaskSource.APP)
        )
        session = start_focus_session(task, now, minutes=minutes)
        self._store_active_focus(session)
        return MobileFocusStart(
            task_id=task.id,
            focus_session_id=session.id,
            title=session.task_title,
            minutes=int(session.duration.total_seconds() // 60),
            started_at=session.started_at.isoformat(),
            ends_at=session.ends_at.isoformat(),
            response_text=_build_focus_response(session=session, notify_external=False),
        )

    def cancel_focus(self, *, now: datetime | None = None) -> bool:
        active = self._read_active_focus()
        if active is None:
            return False
        now = _ensure_aware(now or datetime.now(UTC))
        task_id = str(active.get("task_id", ""))
        if task_id:
            with suppress(KeyError):
                self._db.tasks.update_status(task_id, TaskStatus.CANCELLED, completed_at=now)
        self._db.config.delete(_ACTIVE_FOCUS_KEY)
        return True

    def _active_focus(self, now: datetime) -> dict[str, Any] | None:
        active = self._read_active_focus()
        if active is None:
            return None
        ends_at = datetime.fromisoformat(str(active["ends_at"]))
        if ends_at <= now:
            task_id = str(active.get("task_id", ""))
            if task_id:
                with suppress(KeyError):
                    self._db.tasks.update_status(task_id, TaskStatus.DONE, completed_at=ends_at)
            self._db.config.delete(_ACTIVE_FOCUS_KEY)
            return None
        active["remaining_seconds"] = max(0, int((ends_at - now).total_seconds()))
        return active

    def _store_active_focus(self, session: FocusSession) -> None:
        payload = {
            "focus_session_id": session.id,
            "task_id": session.task_id,
            "title": session.task_title,
            "started_at": session.started_at.isoformat(),
            "ends_at": session.ends_at.isoformat(),
            "minutes": int(session.duration.total_seconds() // 60),
        }
        self._db.config.set(_ACTIVE_FOCUS_KEY, json.dumps(payload, ensure_ascii=False))

    def _read_active_focus(self) -> dict[str, Any] | None:
        raw = self._db.config.get(_ACTIVE_FOCUS_KEY)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._db.config.delete(_ACTIVE_FOCUS_KEY)
            return None
        if not isinstance(payload, dict) or "ends_at" not in payload:
            self._db.config.delete(_ACTIVE_FOCUS_KEY)
            return None
        return payload


def status_to_dict(status: MobileStatus) -> dict[str, Any]:
    return asdict(status)


def focus_start_to_dict(result: MobileFocusStart) -> dict[str, Any]:
    return asdict(result)


def _clean_title(title: str | None) -> str:
    clean = " ".join((title or "").strip().split())
    return clean or "Sesión de foco"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
