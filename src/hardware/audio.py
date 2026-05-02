"""Implementaciones in-memory de captura/playback.

`InMemoryCapture` devuelve un buffer prefabricado — útil para tests y
para "modo offline sin micrófono" como fallback degradado. La
implementación real sobre `sounddevice`/`pyaudio` carga lazy y vive
en una clase separada (TODO al provisionar la Pi).
"""

from __future__ import annotations

from voice.types import AudioBuffer


class InMemoryCapture:
    def __init__(self, audio: AudioBuffer) -> None:
        self._audio = audio

    def capture(self, max_seconds: float) -> AudioBuffer:
        if max_seconds <= 0:
            raise ValueError(f"max_seconds must be positive, got {max_seconds}")
        return self._audio


class InMemoryPlayback:
    def __init__(self) -> None:
        self.played: list[AudioBuffer] = []

    def play(self, audio: AudioBuffer) -> None:
        self.played.append(audio)
