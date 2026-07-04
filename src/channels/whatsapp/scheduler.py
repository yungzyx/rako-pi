"""Scheduling policy for proactive WhatsApp check-ins.

The scheduler is deliberately conservative: consent is required, messages are
limited to a daytime window, repeated sends are throttled, and recent user
interaction suppresses another proactive nudge.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from channels.whatsapp.client import WhatsAppOutboundMessage
from channels.whatsapp.service import WhatsAppService
from db.database import Database
from product.user_config import UserConfigService
from productivity.crisis_gate import has_recent_crisis_event

_LAST_CHECKIN_KEY = "whatsapp.last_checkin"


@dataclass(frozen=True, slots=True)
class SmartCheckinDecision:
    should_send: bool
    reason: str
    to: str | None = None


@dataclass(frozen=True, slots=True)
class SmartCheckinSchedule:
    min_interval: timedelta = timedelta(hours=6)
    quiet_start_hour: int = 22
    quiet_end_hour: int = 8
    recent_interaction_window: timedelta = timedelta(minutes=45)

    def __post_init__(self) -> None:
        if self.min_interval <= timedelta():
            raise ValueError("min_interval must be positive")
        if self.recent_interaction_window < timedelta():
            raise ValueError("recent_interaction_window cannot be negative")
        if not 0 <= self.quiet_start_hour <= 23:
            raise ValueError("quiet_start_hour must be 0..23")
        if not 0 <= self.quiet_end_hour <= 23:
            raise ValueError("quiet_end_hour must be 0..23")


def decide_smart_checkin(
    db: Database,
    *,
    now: datetime | None = None,
    schedule: SmartCheckinSchedule | None = None,
) -> SmartCheckinDecision:
    now = _ensure_aware(now or datetime.now(UTC))
    schedule = schedule or SmartCheckinSchedule()
    config = UserConfigService(db)
    channels = config.get_channels()
    if not config.proactive_messages_can_send() or not channels.whatsapp_number:
        return SmartCheckinDecision(should_send=False, reason="consent_required")
    if has_recent_crisis_event(db, now=now):
        return SmartCheckinDecision(
            should_send=False,
            reason="recent_crisis",
            to=channels.whatsapp_number,
        )
    if _is_quiet_hour(now, schedule=schedule):
        return SmartCheckinDecision(
            should_send=False,
            reason="quiet_hours",
            to=channels.whatsapp_number,
        )
    last_sent_at = _last_checkin_at(db)
    if last_sent_at is not None and now - last_sent_at < schedule.min_interval:
        return SmartCheckinDecision(
            should_send=False,
            reason="too_soon",
            to=channels.whatsapp_number,
        )
    if _has_recent_interaction(db, now=now, window=schedule.recent_interaction_window):
        return SmartCheckinDecision(
            should_send=False,
            reason="recent_interaction",
            to=channels.whatsapp_number,
        )
    return SmartCheckinDecision(
        should_send=True,
        reason="eligible",
        to=channels.whatsapp_number,
    )


def send_due_smart_checkin(
    service: WhatsAppService,
    db: Database,
    *,
    now: datetime | None = None,
    schedule: SmartCheckinSchedule | None = None,
) -> WhatsAppOutboundMessage | None:
    now = _ensure_aware(now or datetime.now(UTC))
    decision = decide_smart_checkin(db, now=now, schedule=schedule)
    if not decision.should_send or decision.to is None:
        return None
    return service.send_smart_checkin(to=decision.to, now=now)


def smart_checkin_decision_to_dict(decision: SmartCheckinDecision) -> dict[str, object]:
    return asdict(decision)


def _is_quiet_hour(now: datetime, *, schedule: SmartCheckinSchedule) -> bool:
    hour = now.hour
    if schedule.quiet_start_hour < schedule.quiet_end_hour:
        return schedule.quiet_start_hour <= hour < schedule.quiet_end_hour
    return hour >= schedule.quiet_start_hour or hour < schedule.quiet_end_hour


def _last_checkin_at(db: Database) -> datetime | None:
    raw = db.config.get(_LAST_CHECKIN_KEY)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    sent_at = payload.get("sent_at")
    if not isinstance(sent_at, str):
        return None
    try:
        return _ensure_aware(datetime.fromisoformat(sent_at))
    except ValueError:
        return None


def _has_recent_interaction(db: Database, *, now: datetime, window: timedelta) -> bool:
    if window == timedelta():
        return False
    for interaction in db.interactions.list_recent(limit=20):
        if now - _ensure_aware(interaction.timestamp) <= window:
            return True
    return False


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
