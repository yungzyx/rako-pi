"""Acoustic wake-word detection.

This module is for real audio wake-word engines. It intentionally does not use
cloud STT for wake detection: unusual names like "Rako" are often transcribed as
"gato", "flaco", etc. The STT path remains only a dev fallback.

Production recommendation: Picovoice Porcupine with a custom keyword file for
"Oye Rako" / "Hola Rako" generated in Picovoice Console.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class AcousticWakeWordListener(Protocol):
    def listen_once(self) -> bool: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PorcupineWakeWordConfig:
    access_key: str
    keyword_path: str
    sensitivity: float = 0.65
    device: str | int | None = None

    def __post_init__(self) -> None:
        if not self.access_key:
            raise ValueError("Porcupine access key is required")
        if not self.keyword_path:
            raise ValueError("Porcupine keyword path is required")
        if not Path(self.keyword_path).exists():
            raise FileNotFoundError(self.keyword_path)
        if not 0.0 <= self.sensitivity <= 1.0:
            raise ValueError("Porcupine sensitivity must be in [0, 1]")


class PorcupineWakeWordListener:
    """Listen for a Porcupine keyword from an input device.

    `recorder` exists for tests. In real use, leave it as None and the class
    records from `sounddevice.RawInputStream`.
    """

    def __init__(
        self,
        config: PorcupineWakeWordConfig,
        *,
        recorder: Callable[[int, int], bytes] | None = None,
    ) -> None:
        self._config = config
        self._recorder = recorder
        self._stream = None

        try:
            import pvporcupine
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "pvporcupine is not installed. Install it with `pip install pvporcupine`."
            ) from exc

        self._porcupine = pvporcupine.create(
            access_key=config.access_key,
            keyword_paths=[config.keyword_path],
            sensitivities=[config.sensitivity],
        )

    @property
    def sample_rate(self) -> int:
        return int(self._porcupine.sample_rate)

    @property
    def frame_length(self) -> int:
        return int(self._porcupine.frame_length)

    def listen_once(self) -> bool:
        pcm = self._read_frame()
        return int(self._porcupine.process(pcm)) >= 0

    def close(self) -> None:
        stream = self._stream
        if stream is not None:  # pragma: no cover - real hardware path
            stream.close()
            self._stream = None
        self._porcupine.delete()

    def _read_frame(self) -> list[int]:
        if self._recorder is not None:
            data = self._recorder(self.frame_length, self.sample_rate)
        else:  # pragma: no cover - real hardware path
            data = self._read_frame_from_sounddevice()
        return _pcm16_bytes_to_ints(data)

    def _read_frame_from_sounddevice(self) -> bytes:  # pragma: no cover - hardware path
        import sounddevice as sd

        if self._stream is None:
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_length,
                channels=1,
                dtype="int16",
                device=self._config.device,
            )
            self._stream.start()
        data, _overflowed = self._stream.read(self.frame_length)
        return bytes(data)


def _pcm16_bytes_to_ints(data: bytes) -> list[int]:
    if len(data) % 2 != 0:
        raise ValueError("PCM16 byte length must be even")
    return [int.from_bytes(data[i : i + 2], "little", signed=True) for i in range(0, len(data), 2)]
