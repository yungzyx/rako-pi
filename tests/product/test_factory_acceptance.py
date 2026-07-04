from __future__ import annotations

from datetime import UTC, datetime

from config import Settings
from db.database import Database
from product.factory_acceptance import (
    acceptance_checklist_to_dict,
    build_factory_acceptance_checklist,
)
from product.user_config import UserConfigService


def test_factory_acceptance_fails_missing_required_product_setup(db_conn) -> None:
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_api_token=None,
        openai_api_key=None,
        stt_provider="openai_whisper",
        elevenlabs_api_key=None,
        tts_provider="elevenlabs",
    )

    checklist = build_factory_acceptance_checklist(Database(db_conn), settings)
    failed_names = {item.name for item in checklist.items if item.status == "fail"}

    assert checklist.ready_for_handoff is False
    assert checklist.automatic_failures >= 5
    assert {
        "user profile",
        "wifi ssid",
        "privacy consent",
        "api token",
        "stt credentials",
        "tts credentials",
    }.issubset(failed_names)


def test_factory_acceptance_passes_when_required_board_config_exists(db_conn) -> None:
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_profile({"preferred_name": "Nico", "university": "UDD"})
    config.update_channels(
        {
            "wifi_ssid": "Casa",
            "whatsapp_number": "+56912345678",
            "wellbeing_unit_name": "Unidad de Bienestar",
            "wellbeing_unit_phone": "+56228203419",
        }
    )
    config.update_consent(
        {
            "whatsapp_enabled": True,
            "progress_reports_enabled": True,
            "proactive_messages_enabled": True,
            "wellbeing_escalation_enabled": True,
        },
        now=datetime(2026, 6, 20, 1, 30, tzinfo=UTC),
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

    checklist = build_factory_acceptance_checklist(db, settings)

    assert checklist.ready_for_handoff is True
    assert checklist.automatic_failures == 0
    assert checklist.manual_items == 6
    assert {item.status for item in checklist.items if item.category == "hardware"} == {"manual"}


def test_factory_acceptance_includes_automatic_crisis_bypass_smoke_check(db_conn) -> None:
    settings = Settings(_env_file=None, rako_env="dev")

    checklist = build_factory_acceptance_checklist(Database(db_conn), settings)
    smoke_item = next(item for item in checklist.items if item.name == "crisis bypass smoke test")

    assert smoke_item.category == "safety"
    assert smoke_item.status == "ok"


def test_factory_acceptance_fails_prod_without_sqlite_encryption_key(db_conn) -> None:
    # CLAUDE.md §4.1.6: producción no debe correr sin SQLCipher activo — un
    # dispositivo no debería poder pasar el checklist de fábrica sin cifrado.
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_api_token="local-token",
        openai_api_key="sk-test",
        stt_provider="openai_whisper",
        elevenlabs_api_key="el-test",
        tts_provider="elevenlabs",
    )

    checklist = build_factory_acceptance_checklist(Database(db_conn), settings)
    encryption_item = next(item for item in checklist.items if item.name == "sqlite encryption key")

    assert encryption_item.status == "fail"
    assert checklist.ready_for_handoff is False


def test_factory_acceptance_fails_wellbeing_without_destination(db_conn) -> None:
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_profile({"preferred_name": "Nico"})
    config.update_channels({"wifi_ssid": "Casa"})
    config.update_consent(
        {"wellbeing_escalation_enabled": True},
        now=datetime(2026, 6, 20, 1, 30, tzinfo=UTC),
    )
    settings = Settings(
        _env_file=None,
        rako_env="dev",
        openai_api_key="sk-test",
        stt_provider="openai_whisper",
        elevenlabs_api_key="el-test",
        tts_provider="elevenlabs",
    )

    checklist = build_factory_acceptance_checklist(db, settings)
    wellbeing = next(item for item in checklist.items if item.name == "wellbeing escalation")

    assert checklist.ready_for_handoff is False
    assert wellbeing.status == "fail"
    assert wellbeing.detail == "missing phone"


def test_acceptance_checklist_to_dict_is_json_ready(db_conn) -> None:
    checklist = build_factory_acceptance_checklist(
        Database(db_conn),
        Settings(_env_file=None),
    )

    payload = acceptance_checklist_to_dict(checklist)

    assert payload["ready_for_handoff"] is False
    assert isinstance(payload["items"], list)
    assert set(payload["items"][0]) == {"category", "name", "status", "detail"}
