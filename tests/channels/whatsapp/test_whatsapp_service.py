from __future__ import annotations

from datetime import UTC, datetime, timedelta

from channels.whatsapp.client import InMemoryWhatsAppClient
from channels.whatsapp.service import WhatsAppService
from db.database import Database


def test_send_checkin_uses_safe_short_prompt(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)
    now = datetime(2026, 6, 1, 16, 0, tzinfo=UTC)

    message = service.send_checkin(to="+56912345678", now=now)

    assert message.kind == "CHECKIN"
    assert message.to == "+56912345678"
    assert "¿cómo te sientes" in message.text
    assert db.config.get("whatsapp.last_checkin") is not None


def test_handle_inbound_records_low_mood_and_replies(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)
    now = datetime(2026, 6, 1, 16, 0, tzinfo=UTC)

    result = service.handle_inbound(from_number="+56912345678", text="me siento bajo", now=now)
    samples = db.emotional_states.list_samples_in_window(end=now, lookback=timedelta(minutes=1))

    assert result.action == "MOOD_RECORDED"
    assert result.stored_mood == "low"
    assert samples[0].vector.valence < 0
    assert client.sent[-1].kind == "MOOD_RECORDED"


def test_handle_inbound_starts_focus_from_whatsapp_text(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)
    now = datetime(2026, 6, 1, 16, 0, tzinfo=UTC)

    result = service.handle_inbound(
        from_number="+56912345678",
        text="quiero estudiar cálculo 25 minutos",
        now=now,
    )

    assert result.action == "FOCUS"
    assert result.focus_session_id is not None
    assert "25 minutos para estudiar cálculo" in result.response_text


def test_handle_inbound_crisis_uses_curated_response(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)

    result = service.handle_inbound(
        from_number="+56912345678",
        text="ya no quiero vivir",
        now=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
    )

    assert result.action == "CRISIS"
    assert result.crisis is True
    assert "No tienes que estar solo" in result.response_text
    assert client.sent[-1].kind == "CRISIS"
