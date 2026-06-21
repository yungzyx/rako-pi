from __future__ import annotations

from datetime import UTC, datetime

from config import Settings
from db.database import Database
from product.device_registry import DeviceRegistryService
from product.factory_report import build_factory_report, factory_report_to_dict
from product.user_config import UserConfigService


def test_factory_report_summarizes_setup_and_acceptance(db_conn) -> None:
    db = Database(db_conn)
    settings = Settings(_env_file=None, rako_env="prod", rako_device_id="rako-001")

    report = build_factory_report(
        db,
        settings,
        app_version="0.1.0",
        now=datetime(2026, 6, 20, 18, 0, tzinfo=UTC),
    )

    assert report.device_id == "rako-001"
    assert report.identity["device_id"] == "rako-001"
    assert report.heartbeat is None
    assert report.environment == "prod"
    assert report.ready_for_handoff is False
    assert report.setup_ready is False
    assert report.next_setup_step_id == "profile"
    assert report.generated_at == "2026-06-20T18:00:00+00:00"


def test_factory_report_is_ready_when_product_setup_is_complete(db_conn) -> None:
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
        sqlite_encryption_key="x" * 64,
        openai_api_key="sk-test",
        stt_provider="openai_whisper",
        elevenlabs_api_key="el-test",
        tts_provider="elevenlabs",
    )

    report = build_factory_report(db, settings, app_version="0.1.0")
    payload = factory_report_to_dict(report)

    assert payload["ready_for_handoff"] is True
    assert payload["setup_ready"] is True
    assert payload["automatic_failures"] == 0
    assert payload["manual_items"] == 6


def test_factory_report_includes_provisioning_and_heartbeat(db_conn) -> None:
    db = Database(db_conn)
    settings = Settings(_env_file=None, rako_env="prod", rako_device_id="rako-001")

    registry = DeviceRegistryService(db, settings)
    registry.provision(serial="SN-001", lot="pilot-a", assigned_user_label="nico@udd")
    registry.heartbeat(app_version="0.1.0", status="ok")

    payload = factory_report_to_dict(build_factory_report(db, settings, app_version="0.1.0"))

    assert payload["identity"]["serial"] == "SN-001"
    assert payload["identity"]["lot"] == "pilot-a"
    assert payload["identity"]["assigned_user_label"] == "nico@udd"
    assert payload["heartbeat"]["status"] == "ok"
