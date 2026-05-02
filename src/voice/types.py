"""Tipos del módulo de voz.

Inmutables. `AudioBuffer` carga el formato implícito en metadata para
no atarse al SDK de un proveedor. Cuando se persiste audio (solo TTS
output, NUNCA audio de usuario), se hace bajo `src/safety/prerecorded/`.
"""

from __future__ import annotations

from dataclasses import dataclass


_LINEAR16_BYTES_PER_SAMPLE = 2


@dataclass(frozen=True, slots=True)
class AudioBuffer:
    data: bytes
    sample_rate: int
    encoding: str

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if not self.encoding:
            raise ValueError("encoding must be a non-empty string")

    @property
    def duration_seconds(self) -> float | None:
        """Duración en segundos para PCM lineal; None para formatos comprimidos."""
        if self.encoding == "LINEAR16":
            return len(self.data) / (self.sample_rate * _LINEAR16_BYTES_PER_SAMPLE)
        return None


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    text: str
    confidence: float
    language: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range [0,1]: {self.confidence!r}")


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    audio: AudioBuffer
    voice_name: str
    text_synthesized: str
