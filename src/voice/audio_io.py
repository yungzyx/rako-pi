"""Protocols de I/O de audio.

Definen el contrato que el orquestador y los clientes STT/TTS consumen.
Las implementaciones concretas viven en `hardware/` (la Pi usa
`sounddevice`/`pyaudio`); en tests se usan fakes en memoria.
"""

from __future__ import annotations

from typing import Protocol

from voice.types import AudioBuffer


class AudioCaptureSource(Protocol):
    def capture(self, max_seconds: float) -> AudioBuffer: ...


class AudioPlaybackSink(Protocol):
    def play(self, audio: AudioBuffer) -> None: ...
