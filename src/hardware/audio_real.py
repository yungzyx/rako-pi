"""Captura y reproducción de audio sobre `sounddevice`.

Wrappers inyectables: el `recorder` y el `player` son callables que
los tests pueden falsificar. Las factories Pi-only construyen los
callables que efectivamente tocan el hardware.
"""

from __future__ import annotations

from collections.abc import Callable

from voice.types import AudioBuffer


class SoundDeviceCapture:
    def __init__(
        self,
        *,
        recorder: Callable[[int, int], bytes],
        sample_rate: int = 16000,
    ) -> None:
        self._recorder = recorder
        self._sample_rate = sample_rate

    def capture(self, max_seconds: float) -> AudioBuffer:
        if max_seconds <= 0:
            raise ValueError(f"max_seconds must be positive, got {max_seconds}")
        frames = int(max_seconds * self._sample_rate)
        data = self._recorder(frames, self._sample_rate)
        return AudioBuffer(
            data=data,
            sample_rate=self._sample_rate,
            encoding="LINEAR16",
        )


class SoundDevicePlayback:
    def __init__(self, *, player: Callable[[bytes, int], None]) -> None:
        self._player = player

    def play(self, audio: AudioBuffer) -> None:
        self._player(audio.data, audio.sample_rate)


def create_pi_capture(  # pragma: no cover - Pi only
    *, sample_rate: int = 16000
) -> SoundDeviceCapture:
    import sounddevice as sd  # type: ignore[import-not-found]

    def recorder(frames: int, sr: int) -> bytes:
        rec = sd.rec(frames, samplerate=sr, channels=1, dtype="int16")
        sd.wait()
        return rec.tobytes()

    return SoundDeviceCapture(recorder=recorder, sample_rate=sample_rate)


def create_pi_playback() -> SoundDevicePlayback:  # pragma: no cover - Pi only
    import io
    import wave

    import sounddevice as sd  # type: ignore[import-not-found]

    def player(data: bytes, sample_rate: int) -> None:
        # Si llega LINEAR16 raw, lo reproducimos directo. Si llega MP3
        # (output de TTS), decodificamos vía `pydub` o equivalente —
        # al provisionar la Pi.
        with wave.open(io.BytesIO(data)) as wav:
            audio_array = wav.readframes(wav.getnframes())
        sd.play(audio_array, samplerate=sample_rate)
        sd.wait()

    return SoundDevicePlayback(player=player)
