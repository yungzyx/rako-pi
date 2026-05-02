"""Tests de los tipos del módulo de voz."""

from __future__ import annotations

import pytest

from voice.types import AudioBuffer, SynthesisResult, TranscriptResult


def test_audio_buffer_construction() -> None:
    buf = AudioBuffer(data=b"\x00\x00", sample_rate=16000, encoding="LINEAR16")

    assert buf.data == b"\x00\x00"
    assert buf.sample_rate == 16000
    assert buf.encoding == "LINEAR16"


def test_audio_buffer_duration_for_linear16() -> None:
    # 16kHz LINEAR16 = 2 bytes/sample → 32000 bytes per second.
    one_second = b"\x00" * 32000
    buf = AudioBuffer(data=one_second, sample_rate=16000, encoding="LINEAR16")

    assert buf.duration_seconds == pytest.approx(1.0, rel=1e-3)


def test_audio_buffer_duration_unknown_for_compressed() -> None:
    buf = AudioBuffer(data=b"...", sample_rate=22050, encoding="MP3")

    assert buf.duration_seconds is None


def test_audio_buffer_rejects_invalid_sample_rate() -> None:
    with pytest.raises(ValueError):
        AudioBuffer(data=b"", sample_rate=0, encoding="LINEAR16")


def test_audio_buffer_rejects_empty_encoding() -> None:
    with pytest.raises(ValueError):
        AudioBuffer(data=b"", sample_rate=16000, encoding="")


def test_audio_buffer_is_immutable() -> None:
    buf = AudioBuffer(data=b"", sample_rate=16000, encoding="LINEAR16")

    with pytest.raises(Exception):
        buf.sample_rate = 8000  # type: ignore[misc]


def test_transcript_result_construction() -> None:
    result = TranscriptResult(text="hola rako", confidence=0.92, language="es-CL")

    assert result.text == "hola rako"
    assert result.confidence == 0.92
    assert result.language == "es-CL"


def test_transcript_result_validates_confidence_range() -> None:
    for bad in (-0.1, 1.1):
        with pytest.raises(ValueError):
            TranscriptResult(text="x", confidence=bad, language="es-CL")


def test_synthesis_result_round_trip() -> None:
    audio = AudioBuffer(data=b"...", sample_rate=22050, encoding="MP3")
    result = SynthesisResult(audio=audio, voice_name="es-CL-Neural2-A", text_synthesized="hola")

    assert result.audio is audio
    assert result.voice_name == "es-CL-Neural2-A"
    assert result.text_synthesized == "hola"
