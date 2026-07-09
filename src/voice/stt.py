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

        # Google divide un enunciado largo en varios `results` consecutivos;
        # tomar solo el primero cortaba el final de frases largas ("estudiar
        # cálculo... y también física" → solo "estudiar cálculo"). Unimos el
        # mejor alternativo de cada segmento y usamos la confianza más baja
        # (conservador) para no sobrestimar la calidad del reconocimiento.
        parts: list[str] = []
        confidences: list[float] = []
        for result in response.results:
            if not result.alternatives:
                continue
            top = result.alternatives[0]
            segment = top.transcript.strip()
            if segment:
                parts.append(segment)
                confidences.append(max(0.0, min(1.0, float(top.confidence))))

        if not parts:
            raise ValueError("STT result had no alternatives")

        return TranscriptResult(
            text=" ".join(parts),
            confidence=min(confidences),
            language=self._language,
        )
