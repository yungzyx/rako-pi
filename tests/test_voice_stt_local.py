"""Tests del STT local de fallback (whisper.cpp) y su cadena."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from voice.stt_local import FallbackSTT, WhisperCppSTT
from voice.types import AudioBuffer, TranscriptResult

_PCM_SILENCE = b"\x00\x00" * 1600


def _audio() -> AudioBuffer:
    return AudioBuffer(data=_PCM_SILENCE, sample_rate=16000, encoding="LINEAR16")


def _fake_whisper_binary(tmp_path: Path, *, output: str) -> str:
    script = tmp_path / "fake-whisper"
    script.write_text(f"#!/bin/sh\necho '{output}'\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_whisper_cpp_transcribes_via_binary(tmp_path: Path) -> None:
    binary = _fake_whisper_binary(tmp_path, output=" hola   rako ")
    model = tmp_path / "model.bin"
    model.write_bytes(b"fake")
    client = WhisperCppSTT(binary_path=binary, model_path=str(model))

    result = client.transcribe(_audio())

    assert result.text == "hola rako"
    assert result.language == "es"
    assert 0.0 < result.confidence < 1.0


def test_whisper_cpp_empty_audio_short_circuits(tmp_path: Path) -> None:
    client = WhisperCppSTT(binary_path="/nonexistent", model_path="/nonexistent")

    result = client.transcribe(AudioBuffer(data=b"", sample_rate=16000, encoding="LINEAR16"))

    assert result.text == ""
    assert result.confidence == 0.0


class _StaticSTT:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
        self.calls += 1
        return TranscriptResult(text=self._text, confidence=0.9, language="es-CL")


class _FailingSTT:
    def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
        raise RuntimeError("network down")


def test_fallback_stt_uses_primary_when_it_works() -> None:
    primary = _StaticSTT("desde el cloud")
    local = _StaticSTT("desde whisper local")

    result = FallbackSTT((primary, local)).transcribe(_audio())

    assert result.text == "desde el cloud"
    assert local.calls == 0


def test_fallback_stt_falls_to_local_on_cloud_failure() -> None:
    local = _StaticSTT("desde whisper local")

    result = FallbackSTT((_FailingSTT(), local)).transcribe(_audio())

    assert result.text == "desde whisper local"


def test_fallback_stt_raises_last_error_when_all_fail() -> None:
    with pytest.raises(RuntimeError, match="network down"):
        FallbackSTT((_FailingSTT(), _FailingSTT())).transcribe(_audio())


def test_fallback_stt_requires_clients() -> None:
    with pytest.raises(ValueError):
        FallbackSTT(())
