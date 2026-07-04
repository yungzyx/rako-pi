"""Tests del cache de TTS pre-sintetizado (voz offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voice.tts_cache import PrerecordedTTS
from voice.types import AudioBuffer, SynthesisResult


def _result(data: bytes = b"AUDIO") -> SynthesisResult:
    return SynthesisResult(
        audio=AudioBuffer(data=data, sample_rate=44100, encoding="MP3"),
        voice_name="elevenlabs:test",
        text_synthesized="hola",
    )


def test_store_then_synthesize_roundtrip(tmp_path: Path) -> None:
    cache = PrerecordedTTS(tmp_path / "cache")
    cache.store("Eso que dijiste me importa.", _result(b"CRISIS-AUDIO"))

    result = cache.synthesize("Eso que dijiste me importa.")

    assert result.audio.data == b"CRISIS-AUDIO"
    assert result.voice_name == "prerecorded-cache"


def test_lookup_is_whitespace_insensitive(tmp_path: Path) -> None:
    cache = PrerecordedTTS(tmp_path / "cache")
    cache.store("Eso que dijiste  me importa.", _result())

    assert cache.has("  Eso que dijiste me importa.  ")
    assert cache.synthesize("Eso que\ndijiste me importa.").audio.data == b"AUDIO"


def test_missing_text_raises_file_not_found(tmp_path: Path) -> None:
    cache = PrerecordedTTS(tmp_path / "cache")

    with pytest.raises(FileNotFoundError):
        cache.synthesize("frase que nadie pregeneró")


def test_empty_text_is_rejected(tmp_path: Path) -> None:
    cache = PrerecordedTTS(tmp_path / "cache")

    with pytest.raises(ValueError):
        cache.synthesize("   ")
    with pytest.raises(ValueError):
        cache.store("", _result())


def test_index_records_text_for_inspection(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = PrerecordedTTS(cache_dir)
    path = cache.store("Hola, estoy aquí contigo.", _result())

    index = json.loads((cache_dir / "index.json").read_text(encoding="utf-8"))
    assert index[path.name]["text"] == "Hola, estoy aquí contigo."
    assert cache.entry_count() == 1


def test_entry_count_zero_without_directory(tmp_path: Path) -> None:
    assert PrerecordedTTS(tmp_path / "nope").entry_count() == 0
