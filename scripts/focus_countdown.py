"""Run a complete focus countdown with OLED timer and spoken completion.

Intended to be launched by `rako-chat` after a focus intent is detected.
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import time

from button_conversation import _play_cue, _synthesize_and_maybe_play

from bootstrap import build_pi_application
from config import Settings

try:  # pragma: no cover - exercised on Pi hardware
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - dev env fallback
    i2c = None
    ssd1306 = None
    Image = None
    ImageDraw = None
    ImageFont = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Rako focus countdown")
    parser.add_argument("--title", required=True)
    parser.add_argument("--minutes", type=int, required=True)
    parser.add_argument(
        "--seconds", type=int, default=None, help="Override duration for quick tests"
    )
    parser.add_argument("--audio-device", default="plughw:seeed2micvoicec,0")
    parser.add_argument("--cue-volume", type=float, default=0.14)
    parser.add_argument("--playback-warmup-seconds", type=float, default=0.55)
    parser.add_argument("--no-playback", action="store_true")
    parser.add_argument("--no-cues", action="store_true")
    parser.add_argument("--no-oled", action="store_true")
    parser.add_argument(
        "--no-chunked-tts",
        action="store_true",
        help="Synthesize the completion phrase in one call instead of sentence by sentence",
    )
    parser.add_argument(
        "--no-stream-tts",
        action="store_true",
        help="Disable provider audio streaming; fall back to chunked/single synthesis",
    )
    parser.add_argument("--tick-seconds", type=float, default=1.0)
    args = parser.parse_args()

    total_seconds = max(1, int(args.seconds if args.seconds is not None else args.minutes * 60))
    print(f"Focus countdown started: {args.title} ({args.minutes} min)", flush=True)
    _run_countdown(
        title=args.title,
        total_seconds=total_seconds,
        tick_seconds=max(0.2, args.tick_seconds),
        oled=not args.no_oled,
    )
    _finish_focus(args)
    return 0


def _run_countdown(*, title: str, total_seconds: int, tick_seconds: float, oled: bool) -> None:
    device = _open_oled() if oled else None
    started = time.monotonic()
    while True:
        elapsed = time.monotonic() - started
        remaining = max(0, total_seconds - int(elapsed))
        if device is not None:
            _draw_countdown(device, title=title, remaining=remaining, total=total_seconds)
        if remaining <= 0:
            break
        time.sleep(min(tick_seconds, remaining))


def _finish_focus(args: argparse.Namespace) -> None:
    if not args.no_cues:
        _play_cue(kind="reply_start", args=args)
    app = build_pi_application(Settings())
    try:
        text = (
            f"Terminaste tu bloque de foco para {args.title}. Buen trabajo. "
            "Descansa cinco minutos: toma agua, estira el cuello, y después vemos si seguimos con otro bloque."
        )
        _synthesize_and_maybe_play(app=app, text=text, args=args)
    finally:
        app.close()
    _show_done_face(seconds=4, oled=not args.no_oled)


def _open_oled():
    if i2c is None or ssd1306 is None:
        return None
    try:
        serial = i2c(port=1, address=0x3C)
        return ssd1306(serial)
    except Exception:
        return None


def _draw_countdown(device, *, title: str, remaining: int, total: int) -> None:
    if Image is None or ImageDraw is None:
        return
    image = Image.new("1", (128, 64))
    draw = ImageDraw.Draw(image)
    minutes, seconds = divmod(remaining, 60)
    timer = f"{minutes:02d}:{seconds:02d}"
    progress = 1 - (remaining / max(1, total))
    bar_width = int(120 * progress)
    title = _short_title(title)
    draw.text((4, 2), "FOCO", fill=255)
    draw.text((4, 14), title, fill=255)
    draw.text((22, 29), timer, fill=255)
    draw.rectangle((4, 56, 124, 61), outline=255)
    draw.rectangle((4, 56, 4 + bar_width, 61), fill=255)
    pulse = int(2 * math.sin(time.monotonic() * 4))
    draw.ellipse((112, 4 + pulse, 122, 14 + pulse), outline=255, fill=255)
    device.display(image)


def _show_done_face(*, seconds: float, oled: bool) -> None:
    if not oled:
        return
    if shutil.which(sys.executable):
        subprocess.run([sys.executable, "eyes.py", "happy", "--seconds", str(seconds)], check=False)


def _short_title(title: str) -> str:
    clean = " ".join(title.split())
    return clean[:18] + ("…" if len(clean) > 18 else "")


if __name__ == "__main__":
    raise SystemExit(main())
