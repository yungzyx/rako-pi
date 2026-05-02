"""Tests de captura/playback real (sounddevice wrappers)."""

from __future__ import annotations

import pytest

from hardware.audio_real import SoundDeviceCapture, SoundDevicePlayback
from voice.types import AudioBuffer


def test_capture_calls_recorder_with_correct_frame_count() -> None:
    calls = []

    def fake_recorder(frames: int, sample_rate: int) -> bytes:
        calls.append((frames, sample_rate))
        return b"\x00" * (frames * 2)

    cap = SoundDeviceCapture(recorder=fake_recorder, sample_rate=16000)

    audio = cap.capture(max_seconds=2.0)

    assert calls == [(32000, 16000)]
    assert isinstance(audio, AudioBuffer)
    assert audio.sample_rate == 16000
    assert audio.encoding == "LINEAR16"
    assert len(audio.data) == 64000  # 32000 frames * 2 bytes


def test_capture_rejects_non_positive_max_seconds() -> None:
    cap = SoundDeviceCapture(recorder=lambda f, sr: b"", sample_rate=16000)

    for bad in (0, -1):
        with pytest.raises(ValueError):
            cap.capture(max_seconds=bad)


def test_playback_calls_player_with_audio_data() -> None:
    plays = []

    def fake_player(data: bytes, sample_rate: int) -> None:
        plays.append((data, sample_rate))

    sink = SoundDevicePlayback(player=fake_player)
    audio = AudioBuffer(data=b"\x00\x01\x02", sample_rate=22050, encoding="MP3")

    sink.play(audio)

    assert plays == [(b"\x00\x01\x02", 22050)]
