"""OpenAI Whisper / audio transcription STT client.

Wraps the OpenAI SDK behind the same `STTClient` protocol as GoogleCloudSTT.
The input audio is converted to an in-memory WAV; no user audio is persisted.
"""

from __future__ import annotations

import io
import wave
from typing import Any

from voice.types import AudioBuffer, TranscriptResult

_LOW_VALUE_TRANSCRIPTS = (
    "subtítulos realizados por la comunidad de amara.org",
    "subtitulos realizados por la comunidad de amara.org",
)


class OpenAIWhisperSTT:
    def __init__(self, client: Any, *, model: str, language: str) -> None:
        self._client = client
        self._model = model
        self._language = language

    def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
        if not audio.data:
            raise ValueError("cannot transcribe empty audio buffer")
        wav = _audio_to_wav_file(audio)
        response = self._client.audio.transcriptions.create(
            model=self._model,
            file=wav,
            language=_language_to_iso639_1(self._language),
        )
        text = getattr(response, "text", "").strip()
        if not text or text.lower() in _LOW_VALUE_TRANSCRIPTS:
            raise ValueError("OpenAI STT returned empty or low-value transcription")
        return TranscriptResult(text=text, confidence=0.0, language=self._language)


def _audio_to_wav_file(audio: AudioBuffer) -> io.BytesIO:
    if audio.encoding != "LINEAR16":
        raise ValueError(f"unsupported audio encoding for OpenAI STT: {audio.encoding}")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(audio.sample_rate)
        wav.writeframes(audio.data)
    buffer.seek(0)
    buffer.name = "rako-input.wav"
    return buffer


def _language_to_iso639_1(language: str) -> str:
    return language.split("-", maxsplit=1)[0].lower() or "es"
