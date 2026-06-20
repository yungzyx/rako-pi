from __future__ import annotations

from datetime import UTC, datetime

from config import Settings
from db.database import Database
from product.setup_flow import build_setup_flow, setup_flow_to_dict
from product.user_config import UserConfigService


def test_setup_flow_starts_with_required_onboarding_steps(db_conn) -> None:
    flow = build_setup_flow(
        Database(db_conn),
        Settings(_env_file=None, rako_env="dev"),
    )
    payload = setup_flow_to_dict(flow)

    assert payload["ready_for_user"] is False
    assert payload["completion_percent"] == 0
    assert payload["next_step_id"] == "profile"
    assert "preferred_name" in payload["missing_required"]
    assert "contraseña WiFi" in payload["privacy_notes"][0]
    assert payload["steps"][0]["status"] == "todo"


def test_setup_flow_marks_ready_when_required_user_and_software_config_exists(db_conn) -> None:
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
            "proactive_messages_enabled": True,
            "progress_reports_enabled": True,
            "wellbeing_escalation_enabled": True,
        },
        now=datetime(2026, 6, 20, 2, 20, tzinfo=UTC),
    )
    config.add_memory(text="Prefiere bloques de 25 minutos", category="routine")
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_api_token="token",
        sqlite_encryption_key="x" * 64,
        openai_api_key="sk-test",
        stt_provider="openai_whisper",
        elevenlabs_api_key="el-test",
        tts_provider="elevenlabs",
    )

    flow = build_setup_flow(db, settings)
    steps = {step.id: step for step in flow.steps}

    assert flow.ready_for_user is True
    assert flow.completion_percent == 100
    assert flow.next_step_id is None
    assert steps["whatsapp"].status == "done"
    assert steps["proactive"].status == "done"
    assert steps["wellbeing"].status == "done"
    assert steps["hardware"].status == "manual"


def test_setup_flow_blocks_when_wellbeing_enabled_without_destination(db_conn) -> None:
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_profile({"preferred_name": "Nico"})
    config.update_channels({"wifi_ssid": "Casa"})
    config.update_consent(
        {"wellbeing_escalation_enabled": True},
        now=datetime(2026, 6, 20, 2, 20, tzinfo=UTC),
    )

    flow = build_setup_flow(
        db,
        Settings(
            _env_file=None,
            rako_env="dev",
            openai_api_key="sk-test",
            stt_provider="openai_whisper",
            elevenlabs_api_key="el-test",
            tts_provider="elevenlabs",
        ),
    )
    wellbeing = next(step for step in flow.steps if step.id == "wellbeing")

    assert flow.ready_for_user is False
    assert flow.next_step_id == "wellbeing"
    assert wellbeing.status == "blocked"
