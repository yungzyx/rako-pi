"""Tests de las implementaciones in-memory de captura/playback de audio."""

from __future__ import annotations

import pytest

from hardware.audio import InMemoryCapture, InMemoryPlayback
from voice.audio_io import AudioCaptureSource, AudioPlaybackSink
from voice.types import AudioBuffer


def _audio() -> AudioBuffer:
    return AudioBuffer(data=b"\x00" * 32000, sample_rate=16000, encoding="LINEAR16")


def test_inmemory_capture_satisfies_protocol() -> None:
    cap: AudioCaptureSource = InMemoryCapture(audio=_audio())
    assert hasattr(cap, "capture")


def test_inmemory_capture_returns_configured_buffer() -> None:
    audio = _audio()
    cap = InMemoryCapture(audio=audio)

    result = cap.capture(max_seconds=5.0)

    assert result is audio


def test_inmemory_capture_rejects_non_positive_max_seconds() -> None:
    cap = InMemoryCapture(audio=_audio())

    with pytest.raises(ValueError):
        cap.capture(max_seconds=0)
    with pytest.raises(ValueError):
        cap.capture(max_seconds=-1)


def test_inmemory_playback_satisfies_protocol_and_records() -> None:
    sink: AudioPlaybackSink = InMemoryPlayback()
    audio = _audio()

    sink.play(audio)
    sink.play(audio)

    assert sink.played == [audio, audio]
