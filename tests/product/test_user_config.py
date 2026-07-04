from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from db.database import Database
from db.types import (
    EmotionalStateRecord,
    Interaction,
    InteractionType,
    Task,
    TaskSource,
    TaskStatus,
)
from emotion.types import EmotionalVector
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


def test_user_data_export_reads_product_config(db_conn) -> None:
    db = Database(db_conn)
    service = UserConfigService(db)
    service.update_profile({"preferred_name": "Nico", "university": "UDD"})
    service.update_channels({"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"})
    service.update_consent({"whatsapp_enabled": True})
    service.add_memory(text="Prefiero estudiar temprano")

    exported = service.export_user_data()

    assert exported["profile"]["preferred_name"] == "Nico"
    assert exported["channels"]["wifi_ssid"] == "Casa"
    assert exported["memory"][0]["text"] == "Prefiero estudiar temprano"


def test_delete_user_data_performs_full_wipe_of_all_local_history(db_conn) -> None:
    # CLAUDE.md §4.1.5: "borrado total ... efecto inmediato" — el borrado
    # debe alcanzar TODO el historial local, no solo la config de producto.
    # Este test reemplaza deliberadamente uno anterior que codificaba el
    # alcance limitado (solo config) como comportamiento esperado: eso era
    # el bug, no la especificación.
    db = Database(db_conn)
    service = UserConfigService(db)
    service.update_profile({"preferred_name": "Nico", "university": "UDD"})
    service.update_channels({"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"})
    service.update_consent({"whatsapp_enabled": True})
    service.add_memory(text="Prefiero estudiar temprano")
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    db.tasks.create(
        Task(
            id="t",
            title="Leer capítulo 3",
            description=None,
            parent_id=None,
            status=TaskStatus.TODO,
            created_at=now,
            completed_at=None,
            source=TaskSource.VOICE,
        )
    )
    db.interactions.append(
        Interaction(
            id="i",
            timestamp=now,
            type=InteractionType.USER_VOICE,
            transcription_excerpt="me siento atascado",
            emotion=None,
            response_id=None,
            response_text=None,
        )
    )
    db.emotional_states.append(
        EmotionalStateRecord(
            id="e",
            at=now,
            vector=EmotionalVector(-0.2, 0.4, 0.5),
            trigger_event=None,
            confidence=0.9,
        )
    )

    deleted = service.delete_user_data()

    assert all(deleted.values())
    assert service.export_user_data()["profile"]["preferred_name"] is None
    assert db.tasks.list_pending() == []
    assert db.interactions.list_recent() == []
    assert db.emotional_states.list_in_window(now, timedelta(days=1)) == []
