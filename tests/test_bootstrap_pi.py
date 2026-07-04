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


def test_build_pi_falls_back_to_fakes_when_real_factories_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si las factories reales fallan, el bootstrap usa los mismos fakes
    que dev. Esto permite ejecutar el binario en mac/CI sin crashear y
    mantiene el test estable en una Raspberry que sí tenga algunas libs."""
    for module in ("gpiozero", "neopixel", "board", "sounddevice"):
        monkeypatch.delitem(sys.modules, module, raising=False)
    monkeypatch.setattr("bootstrap._try_real_leds", lambda: None)
    monkeypatch.setattr("bootstrap._try_real_servos", lambda: None)
    monkeypatch.setattr("bootstrap._try_real_capture", lambda: None)
    monkeypatch.setattr("bootstrap._try_real_playback", lambda: None)

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


def test_try_real_stt_returns_none_without_credentials(tmp_path: Path) -> None:
    from bootstrap import _try_real_stt

    settings = Settings(
        _env_file=None,
        rako_env="prod",
        google_application_credentials=None,
    )
    assert _try_real_stt(settings) is None


def test_try_real_tts_returns_none_without_credentials(tmp_path: Path) -> None:
    from bootstrap import _try_real_tts

    settings = Settings(
        _env_file=None,
        rako_env="prod",
        google_application_credentials=None,
        tts_provider="google",
    )
    assert _try_real_tts(settings) is None


def test_try_real_tts_returns_none_when_elevenlabs_selected_without_key() -> None:
    from bootstrap import _try_real_tts

    settings = Settings(
        _env_file=None,
        rako_env="prod",
        tts_provider="elevenlabs",
        elevenlabs_api_key=None,
    )

    assert _try_real_tts(settings) is None


def test_try_real_tts_prefers_elevenlabs_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bootstrap import _CannedTTS, _try_real_tts

    eleven = _CannedTTS()

    monkeypatch.setattr("bootstrap._try_elevenlabs_tts", lambda settings: eleven)
    monkeypatch.setattr("bootstrap._try_google_tts", lambda settings: None)

    settings = Settings(
        _env_file=None,
        rako_env="prod",
        tts_provider="elevenlabs",
        elevenlabs_api_key="el-test",
    )

    assert _try_real_tts(settings) is eleven


def test_build_pi_uses_canned_stt_tts_without_credentials(tmp_path: Path) -> None:
    from bootstrap import _CannedSTT, _CannedTTS

    app = build_pi_application(_settings(tmp_path))
    try:
        # Sin GOOGLE_APPLICATION_CREDENTIALS caemos a canned, no crash.
        assert isinstance(app.stt, _CannedSTT)
        assert isinstance(app.tts, _CannedTTS)
    finally:
        app.close()


def test_try_real_tts_wraps_multiple_candidates_in_fallback_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bootstrap import _CannedTTS, _try_real_tts
    from voice.tts import FallbackTTS

    eleven = _CannedTTS()
    google = _CannedTTS()

    monkeypatch.setattr("bootstrap._try_elevenlabs_tts", lambda settings: eleven)
    monkeypatch.setattr("bootstrap._try_google_tts", lambda settings: google)

    settings = Settings(
        _env_file=None,
        rako_env="prod",
        tts_provider="elevenlabs",
        elevenlabs_api_key="el-test",
        google_application_credentials="creds.json",
    )

    tts = _try_real_tts(settings)

    assert isinstance(tts, FallbackTTS)
    assert tts.clients == (eleven, google)


def test_build_pi_wires_real_crisis_notifier(tmp_path: Path) -> None:
    from bootstrap import build_pi_application
    from channels.whatsapp.client import InMemoryWhatsAppClient
    from channels.whatsapp.crisis_notifier import WhatsAppCrisisNotifier

    settings = Settings(
        _env_file=None,
        rako_env="dev",
        sqlite_path=str(tmp_path / "rako.db"),
        anthropic_api_key=None,
        obsidian_vault_path=str(tmp_path / "vault"),
        chroma_db_path=str(tmp_path / "chroma"),
    )
    app = build_pi_application(settings)
    try:
        notifier = app.crisis_protocol.notifier
        assert isinstance(notifier, WhatsAppCrisisNotifier)
        # Sin credenciales cloud el cliente es en memoria: cero red.
        assert isinstance(notifier._client, InMemoryWhatsAppClient)
    finally:
        app.close()
