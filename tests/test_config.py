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
