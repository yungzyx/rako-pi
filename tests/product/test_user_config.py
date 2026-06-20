from __future__ import annotations

from datetime import UTC, datetime

import pytest

from db.database import Database
from product.user_config import UserConfigService


def test_onboarding_status_lists_missing_product_requirements(db_conn) -> None:
    service = UserConfigService(Database(db_conn))

    status = service.onboarding_status()

    assert status.ready is False
    assert status.missing == ("preferred_name", "wifi_ssid", "privacy_consent")


def test_profile_channels_and_consent_make_device_ready(db_conn) -> None:
    service = UserConfigService(Database(db_conn))
    now = datetime(2026, 6, 10, 22, 0, tzinfo=UTC)

    profile = service.update_profile({"preferred_name": "Nico", "university": "UDD"})
    channels = service.update_channels({"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"})
    consent = service.update_consent(
        {"whatsapp_enabled": True, "progress_reports_enabled": True},
        now=now,
    )
    status = service.onboarding_status()

    assert profile.preferred_name == "Nico"
    assert channels.wifi_ssid == "Casa"
    assert consent.accepted_at == now.isoformat()
    assert service.whatsapp_can_send() is True
    assert service.progress_reports_can_send() is True
    assert status.ready is True
    assert status.missing == ()


def test_does_not_store_wifi_password(db_conn) -> None:
    service = UserConfigService(Database(db_conn))

    with pytest.raises(ValueError, match="wifi_password"):
        service.update_channels({"wifi_ssid": "Casa", "wifi_password": "secret"})


def test_editable_memory_requires_consent_for_sensitive_items(db_conn) -> None:
    service = UserConfigService(Database(db_conn))

    with pytest.raises(ValueError, match="sensitive memory"):
        service.add_memory(text="Me cuesta pedir ayuda", sensitivity="sensitive")

    service.update_consent({"sensitive_memory_enabled": True})
    memory = service.add_memory(text="Prefiero bloques de 25 minutos", category="routine")

    assert memory.category == "routine"
    assert service.list_memory()[0].text == "Prefiero bloques de 25 minutos"
    assert service.delete_memory(memory.id) is True
    assert service.list_memory() == ()


def test_user_data_export_and_delete_are_limited_to_product_config(db_conn) -> None:
    db = Database(db_conn)
    service = UserConfigService(db)
    service.update_profile({"preferred_name": "Nico", "university": "UDD"})
    service.update_channels({"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"})
    service.update_consent({"whatsapp_enabled": True})
    service.add_memory(text="Prefiero estudiar temprano")
    db.config.set("operational.log.marker", "keep-me")

    exported = service.export_user_data()
    deleted = service.delete_user_data()

    assert exported["profile"]["preferred_name"] == "Nico"
    assert exported["channels"]["wifi_ssid"] == "Casa"
    assert exported["memory"][0]["text"] == "Prefiero estudiar temprano"
    assert all(deleted.values())
    assert service.export_user_data()["profile"]["preferred_name"] is None
    assert db.config.get("operational.log.marker") == "keep-me"
