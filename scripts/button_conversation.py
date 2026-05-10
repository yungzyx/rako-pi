"""Trigger a Rako conversation from a physical GPIO button.

Default target: ReSpeaker 2-Mics Pi HAT user button, commonly wired to BCM GPIO17.

Flow:
    button press -> capture mic audio -> STT -> orchestrator -> TTS -> optional playback

Input audio is never persisted. Only TTS output may be written to /tmp for playback.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/button_conversation.py
    PYTHONPATH=src .venv/bin/python scripts/button_conversation.py --pin 17
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from bootstrap import build_pi_application
from config import Settings
from orchestrator.orchestrator import TurnInput
from orchestrator.types import default_user_context

_DEFAULT_BUTTON_PIN = 17
_DEFAULT_CAPTURE_SECONDS = 5.0
_DEFAULT_AUDIO_OUTPUT_DEVICE = "hw:2,0"  # Raspberry Pi headphone jack


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Use a GPIO button to start a Rako turn")
    parser.add_argument(
        "--pin",
        type=int,
        default=_DEFAULT_BUTTON_PIN,
        help=f"BCM GPIO pin for button (default: {_DEFAULT_BUTTON_PIN})",
    )
    parser.add_argument(
        "--capture-seconds",
        type=float,
        default=_DEFAULT_CAPTURE_SECONDS,
        help=f"Seconds to listen after button press (default: {_DEFAULT_CAPTURE_SECONDS})",
    )
    parser.add_argument(
        "--audio-device",
        default=_DEFAULT_AUDIO_OUTPUT_DEVICE,
        help=f"ALSA device for mpg123 playback (default: {_DEFAULT_AUDIO_OUTPUT_DEVICE})",
    )
    parser.add_argument(
        "--no-playback",
        action="store_true",
        help="Do not try speaker playback; only print and save TTS output",
    )
    args = parser.parse_args(argv)

    if args.capture_seconds <= 0:
        parser.error("--capture-seconds must be positive")

    try:
        from gpiozero import Button
    except Exception as exc:
        print(f"gpiozero is not available: {exc}", file=sys.stderr)
        return 2

    settings = Settings()
    app = build_pi_application(settings)
    button = Button(args.pin, pull_up=True, bounce_time=0.05)

    print(f"Rako button listener ready on BCM GPIO{args.pin}.")
    print("Press the ReSpeaker button, then speak after 'Escuchando...'. Ctrl+C to stop.")

    def handle_press() -> None:
        print("\nBotón detectado. Escuchando...")
        try:
            audio = app.capture.capture(args.capture_seconds)
            transcript = app.stt.transcribe(audio).text.strip()
        except Exception as exc:
            print(f"No pude capturar/transcribir: {exc}")
            return

        if not transcript:
            print("No escuché una frase clara.")
            return

        print(f"Tú: {transcript}")
        now = datetime.now(UTC)
        turn = TurnInput(
            transcript=transcript,
            emotion=None,
            panic_button=None,
            emotion_history=(),
            last_high_distress_at=None,
            last_interaction_at=None,
            user_context=default_user_context(now),
            now=now,
        )
        result = app.orchestrator.handle_turn(turn)
        print(f"Rako: {result.text}")

        try:
            synth = app.tts.synthesize(result.text)
        except Exception as exc:
            print(f"No pude sintetizar voz: {exc}")
            return

        out = Path("/tmp/rako-button-reply.mp3")
        out.write_bytes(synth.audio.data)
        print(f"Audio TTS guardado en {out}")

        if args.no_playback:
            return
        if shutil.which("mpg123") is None:
            print("mpg123 no está instalado; no reproduzco audio automáticamente.")
            return
        subprocess.run(["mpg123", "-q", "-a", args.audio_device, str(out)], check=False)

    button.when_pressed = handle_press

    try:
        while True:
            input()
    except KeyboardInterrupt:
        print("\nDetenido.")
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
