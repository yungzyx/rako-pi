"""Tiny local chill music/ambient mode for Rako.

No streaming account needed: generates a soft ambient WAV and loops it with aplay.
"""

from __future__ import annotations

import argparse
import math
import os
import signal
import struct
import subprocess
import wave
from pathlib import Path

PID_FILE = Path("/tmp/rako-music.pid")
WAV_FILE = Path("/tmp/rako-chill-loop.wav")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rako local chill music mode")
    parser.add_argument("action", choices=("start", "stop", "toggle", "status"))
    parser.add_argument("--audio-device", default="plughw:seeed2micvoicec,0")
    parser.add_argument("--volume", type=float, default=0.08)
    args = parser.parse_args()

    if args.action == "status":
        print("running" if _is_running() else "stopped")
        return 0
    if args.action == "stop":
        _stop()
        print("Rako music stopped")
        return 0
    if args.action == "toggle":
        if _is_running():
            _stop()
            print("Rako music stopped")
        else:
            _start(device=args.audio_device, volume=args.volume)
            print("Rako music started")
        return 0
    _start(device=args.audio_device, volume=args.volume)
    print("Rako music started")
    return 0


def _start(*, device: str, volume: float) -> None:
    if _is_running():
        return
    _write_loop(WAV_FILE, volume=max(0.0, min(0.3, volume)))
    process = subprocess.Popen(
        ["bash", "-lc", f"while true; do aplay -q -D {device!s} {str(WAV_FILE)!s}; done"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")


def _stop() -> None:
    pid = _read_pid()
    if pid is None:
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        os.kill(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)


def _is_running() -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return False
    return True


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _write_loop(path: Path, *, volume: float) -> None:
    if path.exists():
        return
    sample_rate = 44100
    seconds = 12
    notes = (220.0, 277.18, 329.63, 440.0)
    frames = bytearray()
    for i in range(sample_rate * seconds):
        t = i / sample_rate
        amp = 0.5 + 0.5 * math.sin(2 * math.pi * t / seconds)
        sample = 0.0
        for idx, freq in enumerate(notes):
            sample += math.sin(2 * math.pi * freq * t + idx) * 0.22
        sample += math.sin(2 * math.pi * 55 * t) * 0.12
        value = int(32767 * volume * amp * sample)
        frames.extend(struct.pack("<h", max(-32768, min(32767, value))))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))


if __name__ == "__main__":
    raise SystemExit(main())
