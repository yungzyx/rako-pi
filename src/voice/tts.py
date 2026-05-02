"""Cliente Text-to-Speech.

`GoogleCloudTTS` envuelve `google.cloud.texttospeech_v1.TextToSpeechClient`.
Por defecto usa una voz neuronal en español chileno y MP3 como salida.
`max_chars` evita gastar cuotas en textos accidentalmente enormes.
"""

from __future__ import annotations

from typing import Any, Final, Protocol, runtime_checkable

from voice.types import AudioBuffer, SynthesisResult

_DEFAULT_MAX_CHARS: Final[int] = 800


@runtime_checkable
class TTSClient(Protocol):
    def synthesize(self, text: str) -> SynthesisResult: ...


class GoogleCloudTTS:
    def __init__(
        self,
        client: Any,
        *,
        voice_name: str,
        language_code: str,
        speaking_rate: float = 0.95,
        max_chars: int = _DEFAULT_MAX_CHARS,
        sample_rate: int = 22050,
    ) -> None:
        self._client = client
        self._voice_name = voice_name
        self._language_code = language_code
        self._speaking_rate = speaking_rate
        self._max_chars = max_chars
        self._sample_rate = sample_rate

    def synthesize(self, text: str) -> SynthesisResult:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("cannot synthesize empty text")
        if len(cleaned) > self._max_chars:
            raise ValueError(
                f"text too long: {len(cleaned)} chars (max {self._max_chars})"
            )

        response = self._client.synthesize_speech(
            input={"text": cleaned},
            voice={
                "name": self._voice_name,
                "language_code": self._language_code,
            },
            audio_config={
                "audio_encoding": "MP3",
                "speaking_rate": self._speaking_rate,
            },
        )

        if not response.audio_content:
            raise ValueError("TTS returned empty audio content")

        audio = AudioBuffer(
            data=response.audio_content,
            sample_rate=self._sample_rate,
            encoding="MP3",
        )
        return SynthesisResult(
            audio=audio,
            voice_name=self._voice_name,
            text_synthesized=cleaned,
        )
