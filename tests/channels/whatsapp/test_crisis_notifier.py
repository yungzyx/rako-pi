"""Tests del notificador real de crisis vía WhatsApp."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from bootstrap import build_dev_application
from channels.whatsapp.client import InMemoryWhatsAppClient
from channels.whatsapp.crisis_notifier import WhatsAppCrisisNotifier
from config import Settings
from product.user_config import UserConfigService
from safety.types import CrisisLevel, CrisisReason, CrisisSignal


def _signal() -> CrisisSignal:
    return CrisisSignal(
        level=CrisisLevel.CRISIS,
        reasons=(CrisisReason.KEYWORDS_IDEATION,),
        detected_at=datetime(2026, 7, 4, 12, 0, tzinfo=UTC),
    )


def _make(tmp_path: Path) -> tuple[WhatsAppCrisisNotifier, InMemoryWhatsAppClient, object]:
    app = build_dev_application(
        Settings(
            _env_file=None,
            rako_env="dev",
            sqlite_path=str(tmp_path / "rako.db"),
            anthropic_api_key=None,
            obsidian_vault_path=str(tmp_path / "vault"),
            chroma_db_path=str(tmp_path / "chroma"),
        )
    )
    client = InMemoryWhatsAppClient()
    return WhatsAppCrisisNotifier(db=app.db, client=client), client, app


def _grant_consent_and_contact(app, *, phone: str = "+56911112222") -> None:
    service = UserConfigService(app.db)
    service.update_consent({"trusted_contact_alerts_enabled": True})
    service.update_channels({"trusted_contact_name": "Vale", "trusted_contact_phone": phone})


def test_sends_curated_alert_with_consent_and_contact(tmp_path: Path) -> None:
    notifier, client, app = _make(tmp_path)
    _grant_consent_and_contact(app)
    UserConfigService(app.db).update_profile({"preferred_name": "Nico"})

    notifier.notify_trusted_contact(_signal())

    assert len(client.sent) == 1
    message = client.sent[0]
    assert message.to == "+56911112222"
    assert message.kind == "crisis_alert"
    assert "Nico" in message.text
    assert "600 360 7777" in message.text
    # Payload mínimo: nada del evento en sí (nivel, razones, transcripción).
    assert "KEYWORDS" not in message.text
    assert "CRISIS" not in message.text


def test_skips_without_registered_consent(tmp_path: Path) -> None:
    notifier, client, app = _make(tmp_path)
    UserConfigService(app.db).update_channels({"trusted_contact_phone": "+56911112222"})

    notifier.notify_trusted_contact(_signal())

    assert client.sent == []


def test_skips_without_contact_phone(tmp_path: Path) -> None:
    notifier, client, app = _make(tmp_path)
    UserConfigService(app.db).update_consent({"trusted_contact_alerts_enabled": True})

    notifier.notify_trusted_contact(_signal())

    assert client.sent == []


def test_uses_fallback_name_when_profile_is_empty(tmp_path: Path) -> None:
    notifier, client, app = _make(tmp_path)
    _grant_consent_and_contact(app)

    notifier.notify_trusted_contact(_signal())

    assert "la persona que acompaño" in client.sent[0].text


def test_delivery_failure_does_not_break_protocol(tmp_path: Path) -> None:
    class _FailingClient:
        def send_text(self, **kwargs):
            raise RuntimeError("network down")

    _notifier, _, app = _make(tmp_path)
    _grant_consent_and_contact(app)
    failing = WhatsAppCrisisNotifier(db=app.db, client=_FailingClient())

    failing.notify_trusted_contact(_signal())  # no debe levantar


def test_show_resources_counts_locally(tmp_path: Path) -> None:
    notifier, client, _ = _make(tmp_path)

    notifier.show_resources()
    notifier.show_resources()

    assert notifier.resources_shown == 2
    assert client.sent == []
