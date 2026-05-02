"""Tests del bootstrap — factory que arma la Application en modo dev."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap import Application, build_dev_application
from config import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        rako_env="dev",
        sqlite_path=str(tmp_path / "rako.db"),
        anthropic_api_key=None,  # forzar fake LLM
        obsidian_vault_path=str(tmp_path / "missing-vault"),
    )


def test_build_dev_returns_application(tmp_path: Path) -> None:
    app = build_dev_application(_settings(tmp_path))
    try:
        assert isinstance(app, Application)
        assert app.db is not None
        assert app.orchestrator is not None
        assert app.sync is not None
        assert app.event_bus is not None
        assert app.leds is not None
    finally:
        app.close()


def test_build_dev_uses_fake_llm_when_no_api_key(tmp_path: Path) -> None:
    app = build_dev_application(_settings(tmp_path))
    try:
        # El LLM debe ser un fake — no debe ser AnthropicLLMClient.
        from orchestrator.llm_client import AnthropicLLMClient

        assert not isinstance(app.orchestrator._llm, AnthropicLLMClient)  # type: ignore[attr-defined]
    finally:
        app.close()


def test_build_dev_creates_schema(tmp_path: Path) -> None:
    app = build_dev_application(_settings(tmp_path))
    try:
        # Las tablas deben existir.
        from db.schema import EXPECTED_TABLES

        rows = app.db._conn.execute(  # type: ignore[attr-defined]
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in rows}
        for expected in EXPECTED_TABLES:
            assert expected in names
    finally:
        app.close()


def test_build_dev_wires_crisis_lighting_to_leds(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from hardware.types import LEDState
    from safety.types import CrisisLevel, CrisisReason, CrisisSignal

    app = build_dev_application(_settings(tmp_path))
    try:
        signal = CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.PANIC_BUTTON_PHYSICAL,),
            detected_at=datetime.now(timezone.utc),
        )
        app.crisis_protocol.execute(signal)

        # Tras un crisis, los LEDs deben estar en PRESENT.
        assert app.leds.current is LEDState.PRESENT  # type: ignore[attr-defined]
    finally:
        app.close()


def test_application_close_is_idempotent(tmp_path: Path) -> None:
    app = build_dev_application(_settings(tmp_path))

    app.close()
    app.close()  # no debe levantar
