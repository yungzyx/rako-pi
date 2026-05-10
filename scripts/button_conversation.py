"""Trigger a Rako conversation from a physical GPIO button.

Default target: ReSpeaker 2-Mics Pi HAT user button, commonly wired to BCM GPIO17.

Flow:
    button press -> lazy app init -> capture mic audio -> STT -> orchestrator -> TTS -> optional playback

Input audio is never persisted. Only TTS output may be written to /tmp for playback.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/button_conversation.py --no-playback
    PYTHONPATH=src .venv/bin/python scripts/button_conversation.py --pin 17
"""

from __future__ import annotations

import argparse
import math
import shutil
import struct
import subprocess
import tempfile
import wave
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bootstrap import build_pi_application
from config import Settings
from orchestrator.orchestrator import TurnInput
from orchestrator.types import default_user_context
from voice.types import AudioBuffer

_DEFAULT_BUTTON_PIN = 17
_DEFAULT_CAPTURE_SECONDS = 5.0
_DEFAULT_AUDIO_OUTPUT_DEVICE = "hw:2,0"  # Raspberry Pi headphone jack
_DEFAULT_GPIO_CHIP = "gpiochip0"
_DEFAULT_CAPTURE_DEVICE = "plughw:seeed2micvoicec,0"
_DEFAULT_CAPTURE_RATE = 16000


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Use a GPIO button to start a Rako turn")
    parser.add_argument(
        "--pin",
        type=int,
        default=_DEFAULT_BUTTON_PIN,
        help=f"BCM GPIO pin for button (default: {_DEFAULT_BUTTON_PIN})",
    )
    parser.add_argument(
        "--gpio-chip",
        default=_DEFAULT_GPIO_CHIP,
        help=f"GPIO chip for gpiomon backend (default: {_DEFAULT_GPIO_CHIP})",
    )
    parser.add_argument(
        "--backend",
        choices=("gpiomon", "gpiozero", "auto"),
        default="gpiomon",
        help="Button backend. Default is gpiomon because RPi.GPIO edge detection fails on newer kernels.",
    )
    parser.add_argument(
        "--capture-seconds",
        type=float,
        default=_DEFAULT_CAPTURE_SECONDS,
        help=f"Seconds to listen after button press (default: {_DEFAULT_CAPTURE_SECONDS})",
    )
    parser.add_argument(
        "--capture-device",
        default=_DEFAULT_CAPTURE_DEVICE,
        help=f"ALSA arecord device for mic capture (default: {_DEFAULT_CAPTURE_DEVICE})",
    )
    parser.add_argument(
        "--capture-rate",
        type=int,
        default=_DEFAULT_CAPTURE_RATE,
        help=f"Sample rate for STT capture (default: {_DEFAULT_CAPTURE_RATE})",
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
    if args.capture_rate <= 0:
        parser.error("--capture-rate must be positive")

    app_holder: dict[str, Any] = {"app": None}

    print(f"Rako button listener ready on BCM GPIO{args.pin}.", flush=True)
    print("Press the ReSpeaker button, then speak after 'Escuchando...'. Ctrl+C to stop.", flush=True)

    def handle_press() -> None:
        if app_holder["app"] is None:
            print("Inicializando Rako...", flush=True)
            app_holder["app"] = build_pi_application(Settings())
        _handle_press(app=app_holder["app"], capture_seconds=args.capture_seconds, args=args)

    try:
        _run_button_loop(
            pin=args.pin,
            gpio_chip=args.gpio_chip,
            backend=args.backend,
            on_press=handle_press,
        )
    except KeyboardInterrupt:
        print("\nDetenido.", flush=True)
    finally:
        app = app_holder.get("app")
        if app is not None:
            app.close()
    return 0


def _run_button_loop(
    *, pin: int, gpio_chip: str, backend: str, on_press: Callable[[], None]
) -> None:
    if backend == "gpiomon":
        _run_gpiomon_loop(pin=pin, gpio_chip=gpio_chip, on_press=on_press)
        return
    if backend == "gpiozero":
        _run_gpiozero_loop(pin=pin, on_press=on_press)
        return

    try:
        _run_gpiozero_loop(pin=pin, on_press=on_press)
    except Exception as exc:
        print(f"gpiozero button backend failed ({exc}); falling back to gpiomon.", flush=True)
        _run_gpiomon_loop(pin=pin, gpio_chip=gpio_chip, on_press=on_press)


def _run_gpiozero_loop(*, pin: int, on_press: Callable[[], None]) -> None:
    from gpiozero import Button

    button = Button(pin, pull_up=True, bounce_time=0.05)
    button.when_pressed = on_press
    while True:
        input()


def _run_gpiomon_loop(*, pin: int, gpio_chip: str, on_press: Callable[[], None]) -> None:
    if shutil.which("gpiomon") is None:
        raise RuntimeError("gpiomon is not installed")

    print(f"Waiting with gpiomon on {gpio_chip} line {pin} (falling edge).", flush=True)
    while True:
        command = [
            "gpiomon",
            "--chip",
            gpio_chip,
            "--edges",
            "falling",
            "--bias",
            "pull-up",
            "--debounce-period",
            "50ms",
            "--num-events",
            "1",
            str(pin),
        ]
        subprocess.run(command, check=True)
        on_press()


def _handle_press(*, app: Any, capture_seconds: float, args: argparse.Namespace) -> None:
    print("\nBotón detectado. Escuchando...", flush=True)
    try:
        audio = _capture_with_arecord(
            device=args.capture_device,
            sample_rate=args.capture_rate,
            seconds=capture_seconds,
        )
        transcript = app.stt.transcribe(audio).text.strip()
    except Exception as exc:
        print(f"No pude capturar/transcribir: {exc}", flush=True)
        return

    if not transcript:
        print("No escuché una frase clara.", flush=True)
        return

    print(f"Tú: {transcript}", flush=True)
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
    print(f"Rako: {result.text}", flush=True)

    try:
        synth = app.tts.synthesize(result.text)
    except Exception as exc:
        print(f"No pude sintetizar voz: {exc}", flush=True)
        return

    out = Path("/tmp/rako-button-reply.mp3")
    out.write_bytes(synth.audio.data)
    print(f"Audio TTS guardado en {out}", flush=True)

    if args.no_playback:
        return
    if shutil.which("mpg123") is None:
        print("mpg123 no está instalado; no reproduzco audio automáticamente.", flush=True)
        return
    subprocess.run(["mpg123", "-q", "-a", args.audio_device, str(out)], check=False)


def _capture_with_arecord(*, device: str, sample_rate: int, seconds: float) -> AudioBuffer:
    if shutil.which("arecord") is None:
        raise RuntimeError("arecord is not installed")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        command = [
            "arecord",
            "-q",
            "-D",
            device,
            "-f",
            "S16_LE",
            "-c",
            "1",
            "-r",
            str(sample_rate),
            "-d",
            str(max(1, int(math.ceil(seconds)))),
            tmp.name,
        ]
        subprocess.run(command, check=True)
        with wave.open(tmp.name, "rb") as wav:
            data = wav.readframes(wav.getnframes())
            rate = wav.getframerate()
            channels = wav.getnchannels()

    samples = struct.unpack("<" + "h" * (len(data) // 2), data) if data else []
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) if samples else 0.0
    peak = max((abs(sample) for sample in samples), default=0)
    print(
        f"Audio capturado: {channels}ch {rate}Hz, rms={rms:.1f}, peak={peak}",
        flush=True,
    )
    if peak == 0:
        print("Aviso: el audio llegó en silencio total desde ALSA.", flush=True)
    data = _normalize_pcm16(data, target_peak=24_000)
    return AudioBuffer(data=data, sample_rate=rate, encoding="LINEAR16")


def _normalize_pcm16(data: bytes, *, target_peak: int) -> bytes:
    samples = struct.unpack("<" + "h" * (len(data) // 2), data) if data else []
    peak = max((abs(sample) for sample in samples), default=0)
    if peak == 0 or peak <= target_peak:
        return data
    scale = target_peak / peak
    normalized = [max(-32768, min(32767, int(sample * scale))) for sample in samples]
    return struct.pack("<" + "h" * len(normalized), *normalized)


if __name__ == "__main__":
    raise SystemExit(main())
