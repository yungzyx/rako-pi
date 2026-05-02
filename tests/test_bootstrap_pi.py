"""Tests del build_pi_application — graceful degradation cuando libs faltan."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from bootstrap import build_pi_application
from config import Settings
from hardware.leds import FakeLEDController
from hardware.servos import FakeServoController
from voice.audio_io import AudioCaptureSource, AudioPlaybackSink


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        rako_env="prod",
        sqlite_path=str(tmp_path / "rako.db"),
        sqlite_encryption_key=None,
        anthropic_api_key=None,
        obsidian_vault_path=str(tmp_path / "missing-vault"),
        chroma_db_path=str(tmp_path / "chroma"),
    )


def test_build_pi_falls_back_to_fakes_when_libs_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin gpiozero / neopixel / sounddevice, el bootstrap usa los mismos
    fakes que dev. Esto permite ejecutar el binario en mac/CI sin
    crashear en imports inalcanzables."""
    # Aseguramos que las libs Pi NO están en el path (en mac/CI no lo están).
    for module in ("gpiozero", "neopixel", "board", "sounddevice"):
        monkeypatch.delitem(sys.modules, module, raising=False)

    app = build_pi_application(_settings(tmp_path))
    try:
        assert isinstance(app.leds, FakeLEDController)
        assert isinstance(app.servos, FakeServoController)
        # Audio capture/playback son in-memory cuando sounddevice falta.
        assert isinstance(app.capture, AudioCaptureSource)
        assert isinstance(app.playback, AudioPlaybackSink)
    finally:
        app.close()


def test_build_pi_creates_schema(tmp_path: Path) -> None:
    app = build_pi_application(_settings(tmp_path))
    try:
        from db.schema import EXPECTED_TABLES

        rows = app.db._conn.execute(  # type: ignore[attr-defined]
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in rows}
        for expected in EXPECTED_TABLES:
            assert expected in names
    finally:
        app.close()


def test_build_pi_close_is_idempotent(tmp_path: Path) -> None:
    app = build_pi_application(_settings(tmp_path))
    app.close()
    app.close()
