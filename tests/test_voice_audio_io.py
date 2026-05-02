"""Tests de los Protocols de I/O de audio (definición + fakes)."""

from __future__ import annotations

from dataclasses import dataclass, field

from voice.audio_io import AudioCaptureSource, AudioPlaybackSink
from voice.types import AudioBuffer


@dataclass
class _FakeCapture:
    buffer: AudioBuffer

    def capture(self, max_seconds: float) -> AudioBuffer:
        return self.buffer


@dataclass
class _FakePlayback:
    played: list[AudioBuffer] = field(default_factory=list)

    def play(self, audio: AudioBuffer) -> None:
        self.played.append(audio)


def test_capture_protocol_is_satisfied_by_fake() -> None:
    buf = AudioBuffer(data=b"\x00", sample_rate=16000, encoding="LINEAR16")
    fake: AudioCaptureSource = _FakeCapture(buffer=buf)

    assert hasattr(fake, "capture")
    assert fake.capture(max_seconds=5.0) is buf


def test_playback_protocol_is_satisfied_by_fake() -> None:
    fake: AudioPlaybackSink = _FakePlayback()
    buf = AudioBuffer(data=b"\x00", sample_rate=16000, encoding="LINEAR16")

    fake.play(buf)

    assert fake.played == [buf]
