"""Listen from the ReSpeaker mic and trigger on Rako wake words.

This is a hardware smoke-test script, not the final always-on service.
It does not persist input audio. Audio lives only in memory until sent to STT.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/listen_wake_word.py --once
    PYTHONPATH=src .venv/bin/python scripts/listen_wake_word.py

Requirements for real speech detection:
    GOOGLE_APPLICATION_CREDENTIALS must point to a valid Google service account
    with Speech-to-Text enabled. Without cloud STT, this script cannot convert
    "Oye Rako" audio into text yet.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from bootstrap import _try_real_stt
from config import Settings
from voice.types import AudioBuffer
from voice.wake_word import SubstringWakeWordDetector

_DEFAULT_DEVICE_HINT = "seeed-2mic-voicecard"
_DEFAULT_SAMPLE_RATE = 16_000
_DEFAULT_CHUNK_SECONDS = 3.0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Listen for Rako wake words from the mic")
    parser.add_argument("--once", action="store_true", help="Capture one chunk and exit")
    parser.add_argument(
        "--chunk-seconds",
        type=float,
        default=_DEFAULT_CHUNK_SECONDS,
        help=f"Seconds per STT chunk (default: {_DEFAULT_CHUNK_SECONDS})",
    )
    parser.add_argument(
        "--device",
        default=os.environ.get("AUDIO_INPUT_DEVICE") or _DEFAULT_DEVICE_HINT,
        help="sounddevice input device index/name hint (default: ReSpeaker name)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=_DEFAULT_SAMPLE_RATE,
        help=f"Capture sample rate for STT (default: {_DEFAULT_SAMPLE_RATE})",
    )
    args = parser.parse_args(argv)

    if args.chunk_seconds <= 0:
        parser.error("--chunk-seconds must be positive")
    if args.sample_rate <= 0:
        parser.error("--sample-rate must be positive")

    settings = Settings()
    stt = _try_real_stt(settings)
    if stt is None:
        print(
            "No real STT is configured. Set GOOGLE_APPLICATION_CREDENTIALS in .env "
            "or environment to test wake word from microphone.",
            file=sys.stderr,
        )
        return 2

    detector = SubstringWakeWordDetector(settings.wake_words_tuple)
    print("Listening for:", ", ".join(settings.wake_words_tuple))
    print(f"Device hint: {args.device!r} · {args.sample_rate} Hz · {args.chunk_seconds}s chunks")
    print("Say: 'Oye Rako' or 'Hola Rako'. Ctrl+C to stop.")

    try:
        while True:
            audio = _capture_audio(
                device=args.device,
                sample_rate=args.sample_rate,
                seconds=args.chunk_seconds,
            )
            try:
                transcript = stt.transcribe(audio).text.strip()
            except Exception as exc:
                print(f"STT did not return text: {exc}")
                if args.once:
                    return 1
                continue

            if transcript:
                print(f"heard: {transcript}")
            hit = detector.detect(transcript)
            if hit is not None:
                print(f"WAKE_WORD_DETECTED: {hit.phrase}")
                return 0 if args.once else 0

            if args.once:
                print("No wake word detected.")
                return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130


def _capture_audio(*, device: str, sample_rate: int, seconds: float) -> AudioBuffer:
    import sounddevice as sd

    frames = int(sample_rate * seconds)
    recording = sd.rec(
        frames,
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        device=device,
    )
    sd.wait()
    return AudioBuffer(data=recording.tobytes(), sample_rate=sample_rate, encoding="LINEAR16")


if __name__ == "__main__":
    raise SystemExit(main())
