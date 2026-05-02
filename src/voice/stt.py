"""Cliente Speech-to-Text.

`GoogleCloudSTT` envuelve `google.cloud.speech_v1.SpeechClient`. En
tests se inyecta cualquier objeto con `recognize(*, config, audio)`
que devuelva un response con `.results[*].alternatives[*]`.

Restricción: el audio NO se persiste — solo viaja en memoria de la
captura al cliente cloud y el cliente recibe únicamente los bytes y
el lenguaje. Sin metadata identificable.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from voice.types import AudioBuffer, TranscriptResult


@runtime_checkable
class STTClient(Protocol):
    def transcribe(self, audio: AudioBuffer) -> TranscriptResult: ...


class GoogleCloudSTT:
    def __init__(self, client: Any, language: str) -> None:
        self._client = client
        self._language = language

    def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
        if not audio.data:
            raise ValueError("cannot transcribe empty audio buffer")

        response = self._client.recognize(
            config={
                "encoding": audio.encoding,
                "sample_rate_hertz": audio.sample_rate,
                "language_code": self._language,
            },
            audio={"content": audio.data},
        )

        if not response.results:
            raise ValueError("STT returned no transcription results")
        first = response.results[0]
        if not first.alternatives:
            raise ValueError("STT result had no alternatives")
        top = first.alternatives[0]

        confidence = max(0.0, min(1.0, float(top.confidence)))
        return TranscriptResult(
            text=top.transcript,
            confidence=confidence,
            language=self._language,
        )
