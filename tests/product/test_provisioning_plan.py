from __future__ import annotations

from config import Settings
from db.database import Database
from product.device_registry import DeviceRegistryService
from product.provisioning_plan import build_provisioning_plan, provisioning_plan_to_dict
from product.user_config import UserConfigService


def test_provisioning_plan_blocks_missing_device_id(db_conn) -> None:
    db = Database(db_conn)
    settings = Settings(_env_file=None, rako_env="prod", rako_api_token="local-token")

    plan = build_provisioning_plan(db, settings)
    payload = provisioning_plan_to_dict(plan)

    assert payload["ready_for_image"] is False
    assert payload["steps"][0]["name"] == "device id"
    assert payload["steps"][0]["status"] == "fail"


def test_provisioning_plan_collects_factory_readiness(db_conn) -> None:
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_profile({"preferred_name": "Nico", "university": "UDD"})
    config.update_channels(
        {
            "wifi_ssid": "Casa",
            "whatsapp_number": "+56912345678",
            "wellbeing_unit_phone": "+56228203419",
        }
    )
    config.update_consent(
        {
            "whatsapp_enabled": True,
            "progress_reports_enabled": True,
            "proactive_messages_enabled": True,
            "wellbeing_escalation_enabled": True,
        }
    )
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_api_token="local-token",
        rako_device_id="rako-001",
        sqlite_encryption_key="x" * 64,
        openai_api_key="sk-test",
        stt_provider="openai_whisper",
        elevenlabs_api_key="el-test",
        tts_provider="elevenlabs",
        rako_setup_hotspot_enabled=True,
    )
    DeviceRegistryService(db, settings).provision(serial="SN-001", lot="pilot-a")

    plan = build_provisioning_plan(db, settings)
    payload = provisioning_plan_to_dict(plan)

    assert payload["ready_for_image"] is True
    assert payload["ready_for_handoff"] is True
    assert payload["device_id"] == "rako-001"
    assert payload["hotspot"]["status"] == "ready"
    assert {step["name"]: step["status"] for step in payload["steps"]}[
        "acceptance checklist"
    ] == "ok"
