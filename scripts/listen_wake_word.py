"""Listen from the ReSpeaker mic and trigger on Rako wake words.

Preferred mode: Porcupine acoustic wake word with a custom `.ppn` keyword file.
Fallback mode: Google STT + text matcher, useful for dev but less reliable for
unusual names like "Rako".

No input audio is persisted.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from bootstrap import _try_real_stt
from config import Settings
from voice.types import AudioBuffer
from voice.wake_audio import PorcupineWakeWordConfig, PorcupineWakeWordListener
from voice.wake_word import SubstringWakeWordDetector

_DEFAULT_DEVICE_HINT = "seeed-2mic-voicecard"
_DEFAULT_SAMPLE_RATE = 16_000
_DEFAULT_CHUNK_SECONDS = 3.0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Listen for Rako wake words from the mic")
    parser.add_argument("--once", action="store_true", help="Capture one chunk/frame and exit")
    parser.add_argument(
        "--engine",
        choices=("auto", "porcupine", "text_stt"),
        default="auto",
        help="Wake-word engine: auto prefers Porcupine when configured",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=float,
        default=_DEFAULT_CHUNK_SECONDS,
        help=f"Seconds per STT chunk for text_stt fallback (default: {_DEFAULT_CHUNK_SECONDS})",
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
        help=f"Capture sample rate for text_stt fallback (default: {_DEFAULT_SAMPLE_RATE})",
    )
    args = parser.parse_args(argv)

    if args.chunk_seconds <= 0:
        parser.error("--chunk-seconds must be positive")
    if args.sample_rate <= 0:
        parser.error("--sample-rate must be positive")

    settings = Settings()
    engine = _select_engine(args.engine, settings)
    if engine == "porcupine":
        return _run_porcupine(settings=settings, device=args.device, once=args.once)
    return _run_text_stt(settings=settings, args=args)


def _select_engine(requested: str, settings: Settings) -> str:
    if requested != "auto":
        return requested
    if settings.wake_word_engine == "porcupine" or (
        settings.porcupine_access_key and settings.porcupine_keyword_path
    ):
        return "porcupine"
    return "text_stt"


def _run_porcupine(*, settings: Settings, device: str, once: bool) -> int:
    if not settings.porcupine_access_key or not settings.porcupine_keyword_path:
        print(
            "Porcupine is selected but PORCUPINE_ACCESS_KEY and "
            "PORCUPINE_KEYWORD_PATH are not both configured.",
            file=sys.stderr,
        )
        return 2

    try:
        listener = PorcupineWakeWordListener(
            PorcupineWakeWordConfig(
                access_key=settings.porcupine_access_key,
                keyword_path=settings.porcupine_keyword_path,
                sensitivity=settings.porcupine_sensitivity,
                device=device,
            )
        )
    except Exception as exc:
        print(f"Could not start Porcupine wake listener: {exc}", file=sys.stderr)
        return 2

    print("Listening with Porcupine acoustic wake-word engine.")
    print(f"Keyword file: {settings.porcupine_keyword_path}")
    print("Say the trained keyword. Ctrl+C to stop.")
    try:
        while True:
            if listener.listen_once():
                print("WAKE_WORD_DETECTED: porcupine")
                return 0
            if once:
                print("No wake word detected in one Porcupine frame.")
                return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    finally:
        listener.close()


def _run_text_stt(*, settings: Settings, args: argparse.Namespace) -> int:
    stt = _try_real_stt(settings)
    if stt is None:
        print(
            "No real STT is configured. Use Porcupine for reliable wake-word detection, "
            "or set GOOGLE_APPLICATION_CREDENTIALS for the text_stt fallback.",
            file=sys.stderr,
        )
        return 2

    detector = SubstringWakeWordDetector(settings.wake_words_tuple)
    print("Listening with text_stt fallback for:", ", ".join(settings.wake_words_tuple))
    print("Warning: STT may confuse 'Rako' with similar words. Prefer Porcupine.")
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
                return 0

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
