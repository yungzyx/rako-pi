"""Tests del cargador de Settings (.env)."""

from __future__ import annotations

import pytest

from config import Settings


def test_settings_loads_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("RAKO_ENV", raising=False)

    settings = Settings(_env_file=None)

    assert settings.rako_env == "dev"
    assert settings.anthropic_model.startswith("claude-")
    assert settings.rag_top_k == 5
    assert settings.tts_provider == "elevenlabs"


def test_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", "256")
    monkeypatch.setenv("RAKO_ENV", "staging")

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key == "test-key"
    assert settings.anthropic_max_tokens == 256
    assert settings.rako_env == "staging"


def test_anthropic_api_key_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key is None


def test_sqlite_path_defaults_to_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SQLITE_PATH", raising=False)

    settings = Settings(_env_file=None)

    assert "rako.db" in settings.sqlite_path


def test_obsidian_vault_path_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/custom/path")

    settings = Settings(_env_file=None)

    assert settings.obsidian_vault_path == "/custom/path"


def test_tts_provider_and_elevenlabs_settings_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "google")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice-123")
    monkeypatch.setenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")

    settings = Settings(_env_file=None)

    assert settings.tts_provider == "google"
    assert settings.elevenlabs_api_key == "el-test"
    assert settings.elevenlabs_voice_id == "voice-123"
    assert settings.elevenlabs_model == "eleven_flash_v2_5"
