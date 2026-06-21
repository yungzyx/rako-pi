from __future__ import annotations

from datetime import UTC, datetime, timedelta

from config import Settings
from db.database import Database
from db.types import EmotionalStateRecord, Interaction, InteractionType, TaskStatus
from emotion.types import EmotionalVector
from product.device_registry import DeviceRegistryService
from product.user_config import UserConfigService
from productivity.focus import create_focus_task


def test_device_identity_defaults_to_settings_device_id(db_conn) -> None:
    service = DeviceRegistryService(
        Database(db_conn),
        Settings(_env_file=None, rako_device_id="rako-001"),
    )

    identity = service.get_identity()

    assert identity.device_id == "rako-001"
    assert identity.serial is None


def test_device_provision_and_heartbeat_are_persisted(db_conn) -> None:
    db = Database(db_conn)
    service = DeviceRegistryService(db, Settings(_env_file=None, rako_device_id="rako-001"))
    now = datetime(2026, 6, 20, 22, 0, tzinfo=UTC)

    identity = service.provision(
        serial="SN-001",
        lot="pilot-a",
        assigned_user_label="nico@udd",
        now=now,
    )
    heartbeat = service.heartbeat(
        app_version="0.1.0",
        status="ok",
        detail="factory bench",
        now=now,
    )

    assert identity.device_id == "rako-001"
    assert identity.serial == "SN-001"
    assert identity.provisioned_at == now.isoformat()
    assert heartbeat.at == now.isoformat()
    assert service.get_heartbeat() == heartbeat


def test_reset_for_reassignment_preserves_identity_and_clears_user_data(db_conn) -> None:
    db = Database(db_conn)
    settings = Settings(_env_file=None, rako_device_id="rako-001")
    registry = DeviceRegistryService(db, settings)
    registry.provision(serial="SN-001", lot="pilot-a", assigned_user_label="old-user")
    registry.heartbeat(app_version="0.1.0")
    config = UserConfigService(db)
    config.update_profile({"preferred_name": "Nico"})
    config.update_channels({"wifi_ssid": "Casa"})
    config.update_consent({"whatsapp_enabled": True})
    db.config.set("whatsapp.pending.569", "{}")
    task = db.tasks.create(create_focus_task("cálculo", datetime(2026, 6, 20, tzinfo=UTC)))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=datetime(2026, 6, 20, tzinfo=UTC))
    db.interactions.append(
        Interaction(
            id="int-1",
            timestamp=datetime(2026, 6, 20, tzinfo=UTC),
            type=InteractionType.USER_VOICE,
            transcription_excerpt="hola",
            emotion=None,
            response_id=None,
            response_text=None,
        )
    )
    db.emotional_states.append(
        EmotionalStateRecord(
            id="emo-1",
            at=datetime(2026, 6, 20, tzinfo=UTC),
            vector=EmotionalVector(valence=0.1, arousal=0.2, dominance=0.3),
            trigger_event="test",
            confidence=0.7,
        )
    )

    result = registry.reset_for_reassignment()

    assert result.identity.serial == "SN-001"
    assert "product.user_profile" in result.deleted_config_keys
    assert "whatsapp.pending.569" in result.deleted_config_keys
    assert UserConfigService(db).get_profile().preferred_name is None
    assert db.tasks.list_recent(limit=10) == []
    assert db.interactions.list_recent(limit=10) == []
    assert (
        db.emotional_states.list_samples_in_window(
            end=datetime(2026, 6, 20, tzinfo=UTC),
            lookback=timedelta(days=1),
        )
        == ()
    )
    assert registry.get_identity().serial == "SN-001"
    assert registry.get_heartbeat() is not None
