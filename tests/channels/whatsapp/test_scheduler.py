from __future__ import annotations

from datetime import UTC, datetime, timedelta

from channels.whatsapp.client import InMemoryWhatsAppClient
from channels.whatsapp.scheduler import (
    SmartCheckinSchedule,
    decide_smart_checkin,
    send_due_smart_checkin,
)
from channels.whatsapp.service import WhatsAppService
from db.database import Database
from db.types import Interaction, InteractionType
from product.user_config import UserConfigService


def _now(hour: int = 14) -> datetime:
    return datetime(2026, 6, 20, hour, 0, tzinfo=UTC)


def _enable_proactive(db: Database) -> None:
    config = UserConfigService(db)
    config.update_channels({"whatsapp_number": "+56912345678"})
    config.update_consent({"whatsapp_enabled": True, "proactive_messages_enabled": True})


def test_decide_smart_checkin_requires_consent(db_conn) -> None:
    db = Database(db_conn)

    decision = decide_smart_checkin(db, now=_now())

    assert decision.should_send is False
    assert decision.reason == "consent_required"


def test_decide_smart_checkin_respects_quiet_hours(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive(db)

    decision = decide_smart_checkin(db, now=_now(hour=23))

    assert decision.should_send is False
    assert decision.reason == "quiet_hours"


def test_decide_smart_checkin_throttles_recent_checkin(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())
    service.send_smart_checkin(to="+56912345678", now=_now())

    decision = decide_smart_checkin(db, now=_now() + timedelta(hours=2))

    assert decision.should_send is False
    assert decision.reason == "too_soon"


def test_decide_smart_checkin_skips_after_recent_interaction(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive(db)
    db.interactions.append(
        Interaction(
            id="recent",
            timestamp=_now() - timedelta(minutes=5),
            type=InteractionType.USER_VOICE,
            transcription_excerpt="hola",
            emotion=None,
            response_id=None,
            response_text=None,
        )
    )

    decision = decide_smart_checkin(db, now=_now())

    assert decision.should_send is False
    assert decision.reason == "recent_interaction"


def test_send_due_smart_checkin_sends_when_eligible(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive(db)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)

    message = send_due_smart_checkin(service, db, now=_now())

    assert message is not None
    assert message.kind == "SMART_CHECKIN"
    assert client.sent[-1] == message


def test_send_due_smart_checkin_can_use_custom_schedule(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())
    schedule = SmartCheckinSchedule(quiet_start_hour=1, quiet_end_hour=2)

    message = send_due_smart_checkin(service, db, now=_now(hour=23), schedule=schedule)

    assert message is not None
