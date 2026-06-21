from __future__ import annotations

from config import Settings
from db.database import Database
from product.first_run import FirstRunMemory, FirstRunPayload, apply_first_run_setup
from product.user_config import UserConfigService


def test_first_run_setup_configures_user_identity_and_memory(db_conn) -> None:
    db = Database(db_conn)
    settings = Settings(rako_device_id="rako-test-001")

    result = apply_first_run_setup(
        db,
        settings,
        FirstRunPayload(
            profile={
                "preferred_name": "Nico",
                "university": "UDD",
                "program": "Ingeniería",
            },
            consent={
                "whatsapp_enabled": True,
                "progress_reports_enabled": True,
                "proactive_messages_enabled": True,
            },
            channels={"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"},
            memories=(FirstRunMemory(text="Prefiere bloques de 25 minutos"),),
            serial="SN-001",
            lot="pilot-a",
            assigned_user_label="nico@udd",
        ),
    )

    config = UserConfigService(db)
    assert result.ready is True
    assert result.memories_added == 1
    assert result.wifi is not None
    assert result.wifi["status"] == "stored"
    assert result.identity is not None
    assert result.identity["serial"] == "SN-001"
    assert config.get_profile().preferred_name == "Nico"
    assert config.progress_reports_can_send() is True
    assert config.list_memory()[0].text == "Prefiere bloques de 25 minutos"


def test_first_run_wifi_apply_is_blocked_without_apply_gate(db_conn) -> None:
    db = Database(db_conn)
    settings = Settings(rako_device_id="rako-test-001", rako_wifi_apply_enabled=False)

    result = apply_first_run_setup(
        db,
        settings,
        FirstRunPayload(
            profile={"preferred_name": "Nico"},
            consent={},
            channels={"wifi_ssid": "Casa"},
            wifi_password="secret",
            apply_wifi=True,
        ),
    )

    assert result.ready is False
    assert result.wifi is not None
    assert result.wifi["status"] == "blocked"
    assert "WiFi apply is disabled" in result.next_actions[1]
