from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from voice.stt_openai import OpenAIWhisperSTT, _audio_to_wav_file, _language_to_iso639_1
from voice.types import AudioBuffer, TranscriptResult


@dataclass
class _Response:
    text: str


class _FakeTranscriptions:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return self.response


class _FakeAudio:
    def __init__(self, response: _Response) -> None:
        self.transcriptions = _FakeTranscriptions(response)


class _FakeOpenAIClient:
    def __init__(self, response: _Response) -> None:
        self.audio = _FakeAudio(response)


def _audio() -> AudioBuffer:
    return AudioBuffer(data=b"\x00\x01" * 16000, sample_rate=16000, encoding="LINEAR16")


def test_openai_whisper_stt_transcribes_audio() -> None:
    fake = _FakeOpenAIClient(_Response(text="hola rako"))
    stt = OpenAIWhisperSTT(fake, model="whisper-1", language="es-CL")

    result = stt.transcribe(_audio())

    assert isinstance(result, TranscriptResult)
    assert result.text == "hola rako"
    assert result.language == "es-CL"
    call = fake.audio.transcriptions.calls[0]
    assert call["model"] == "whisper-1"
    assert call["language"] == "es"
    assert call["file"].name == "rako-input.wav"


def test_openai_whisper_stt_rejects_empty_audio() -> None:
    fake = _FakeOpenAIClient(_Response(text="x"))
    stt = OpenAIWhisperSTT(fake, model="whisper-1", language="es-CL")

    with pytest.raises(ValueError):
        stt.transcribe(AudioBuffer(data=b"", sample_rate=16000, encoding="LINEAR16"))


def test_openai_whisper_stt_rejects_empty_transcript() -> None:
    fake = _FakeOpenAIClient(_Response(text=""))
    stt = OpenAIWhisperSTT(fake, model="whisper-1", language="es-CL")

    with pytest.raises(ValueError, match="low-value transcription"):
        stt.transcribe(_audio())


def test_openai_whisper_stt_rejects_known_silence_hallucination() -> None:
    fake = _FakeOpenAIClient(_Response(text="Subtítulos realizados por la comunidad de Amara.org"))
    stt = OpenAIWhisperSTT(fake, model="whisper-1", language="es-CL")

    with pytest.raises(ValueError, match="low-value transcription"):
        stt.transcribe(_audio())


def test_audio_to_wav_file_rejects_unsupported_encoding() -> None:
    with pytest.raises(ValueError):
        _audio_to_wav_file(AudioBuffer(data=b"abc", sample_rate=16000, encoding="MP3"))


def test_language_to_iso639_1() -> None:
    assert _language_to_iso639_1("es-CL") == "es"
    assert _language_to_iso639_1("en") == "en"
