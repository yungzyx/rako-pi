"""OLED eye expressions for Rako.

Hardware: 128x64 SSD1306 OLED over I2C at 0x3C.

Examples:
    python eyes.py demo
    python eyes.py happy
    python eyes.py listening --loop
    python eyes.py sleepy --seconds 10
"""

from __future__ import annotations

import argparse
import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image, ImageDraw

WIDTH = 128
HEIGHT = 64
LEFT_EYE = (19, 17, 51, 47)
RIGHT_EYE = (77, 17, 109, 47)

FrameFn = Callable[[ImageDraw.ImageDraw, float], None]


@dataclass(frozen=True)
class Expression:
    name: str
    draw: FrameFn
    frame_delay: float = 0.08
    duration: float = 2.0


def open_device():
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306

    serial = i2c(port=1, address=0x3C)
    return ssd1306(serial)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("1", (WIDTH, HEIGHT))
    return image, ImageDraw.Draw(image)


def eye(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    pupil: tuple[int, int] = (0, 0),
    openness: float = 1.0,
) -> None:
    openness = max(0.15, min(1.0, openness))
    cx = (box[0] + box[2]) // 2
    cy = (box[1] + box[3]) // 2
    half_h = max(3, int(((box[3] - box[1]) / 2) * openness))
    eye_box = (box[0], cy - half_h, box[2], cy + half_h)
    draw.rounded_rectangle(eye_box, radius=9, outline=255, fill=255)
    # Soft eyelid: trimming the top corners makes the face less stare-like.
    if openness > 0.55:
        draw.arc(
            (box[0] + 2, eye_box[1] - 6, box[2] - 2, eye_box[1] + 16), 190, 350, fill=0, width=2
        )
    px = cx + pupil[0]
    py = cy + pupil[1]
    draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=0)
    draw.point((px - 1, py - 2), fill=255)


def soft_eye(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    pupil: tuple[int, int] = (0, 0),
    t: float = 0.0,
    attentive: bool = False,
) -> None:
    blink_cycle = t % 5.2
    openness = 0.18 if blink_cycle < 0.08 else 0.86 + 0.06 * math.sin(t * 1.8)
    if attentive:
        openness = min(1.0, openness + 0.1)
    eye(draw, box, pupil=pupil, openness=openness)


def cheek(draw: ImageDraw.ImageDraw, x: int, y: int, phase: float = 0.0) -> None:
    width = 8 + int(2 * (0.5 + 0.5 * math.sin(phase)))
    draw.arc((x - width, y - 3, x + width, y + 5), 15, 165, fill=255, width=1)


def gentle_smile(draw: ImageDraw.ImageDraw, *, y: int = 51, width: int = 28) -> None:
    left = 64 - width // 2
    right = 64 + width // 2
    draw.arc((left, y - 8, right, y + 8), 20, 160, fill=255, width=2)


def breathe_offset(t: float, amount: int = 2) -> int:
    return int(amount * math.sin(t * 1.7))


def closed_eye(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, tilt: int = 0) -> None:
    y = (box[1] + box[3]) // 2
    draw.line((box[0], y + tilt, box[2], y - tilt), fill=255, width=4)


def brow(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
    draw.line((x1, y1, x2, y2), fill=255, width=3)


def mouth(draw: ImageDraw.ImageDraw, kind: str = "smile") -> None:
    if kind == "smile":
        draw.arc((48, 42, 80, 58), 10, 170, fill=255, width=2)
    elif kind == "sad":
        draw.arc((48, 50, 80, 66), 190, 350, fill=255, width=2)
    elif kind == "flat":
        draw.line((52, 54, 76, 54), fill=255, width=2)
    elif kind == "o":
        draw.ellipse((59, 48, 69, 58), outline=255, width=2)
    elif kind == "small":
        draw.arc((55, 47, 73, 57), 20, 160, fill=255, width=2)


def draw_neutral(draw: ImageDraw.ImageDraw, t: float) -> None:
    y = breathe_offset(t, amount=1)
    soft_eye(draw, _shift(LEFT_EYE, 0, y), t=t)
    soft_eye(draw, _shift(RIGHT_EYE, 0, y), t=t + 0.03)
    gentle_smile(draw, y=52)


def draw_happy(draw: ImageDraw.ImageDraw, t: float) -> None:
    bounce = int(2 * math.sin(t * 5))
    closed_eye(draw, (21, 15 + bounce, 51, 43 + bounce), tilt=-2)
    closed_eye(draw, (77, 15 + bounce, 107, 43 + bounce), tilt=2)
    cheek(draw, 29, 43 + bounce, phase=t * 3)
    cheek(draw, 99, 43 + bounce, phase=t * 3 + 1)
    gentle_smile(draw, y=50 + bounce, width=34)


def draw_sad(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, (21, 22, 51, 47), pupil=(0, 3), openness=0.65)
    eye(draw, (77, 22, 107, 47), pupil=(0, 3), openness=0.65)
    brow(draw, 20, 15, 50, 22)
    brow(draw, 78, 22, 108, 15)
    mouth(draw, "sad")
    if int(t * 2) % 2 == 0:
        draw.line((50, 44, 50, 53), fill=255, width=2)


def draw_sleepy(draw: ImageDraw.ImageDraw, t: float) -> None:
    y = breathe_offset(t, amount=1)
    closed_eye(draw, _shift(LEFT_EYE, 0, y))
    closed_eye(draw, _shift(RIGHT_EYE, 0, y))
    mouth(draw, "flat")
    z = int((t * 12) % 24)
    draw.text((94, 8 - z // 3), "z", fill=255)
    draw.text((104, 18 - z // 2), "Z", fill=255)


def draw_bored(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, (21, 25, 51, 43), pupil=(-2, 2), openness=0.5)
    eye(draw, (77, 25, 107, 43), pupil=(-2, 2), openness=0.5)
    mouth(draw, "flat")


def draw_surprised(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, (17, 12, 53, 50), pupil=(0, 0), openness=1.0)
    eye(draw, (75, 12, 111, 50), pupil=(0, 0), openness=1.0)
    mouth(draw, "o")


def draw_wink(draw: ImageDraw.ImageDraw, t: float) -> None:
    soft_eye(draw, LEFT_EYE, pupil=(2, 0), t=t, attentive=True)
    closed_eye(draw, RIGHT_EYE, tilt=1)
    cheek(draw, 95, 43, phase=t)
    gentle_smile(draw)


def draw_thinking(draw: ImageDraw.ImageDraw, t: float) -> None:
    offset = int(6 * math.sin(t * 2))
    soft_eye(draw, LEFT_EYE, pupil=(offset // 2, -1), t=t)
    soft_eye(draw, RIGHT_EYE, pupil=(offset // 2, -1), t=t + 0.08)
    for i in range(3):
        r = 1 + i
        x = 92 + i * 10
        y = 8 + int(2 * math.sin(t * 3 + i))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


def draw_listening(draw: ImageDraw.ImageDraw, t: float) -> None:
    pulse = int(4 * (0.5 + 0.5 * math.sin(t * 8)))
    soft_eye(draw, LEFT_EYE, pupil=(-1, 0), t=t, attentive=True)
    soft_eye(draw, RIGHT_EYE, pupil=(1, 0), t=t, attentive=True)
    draw.arc((5, 22 - pulse, 21, 42 + pulse), -55, 55, fill=255, width=1)
    draw.arc((107, 22 - pulse, 123, 42 + pulse), 125, 235, fill=255, width=1)
    draw.arc((0, 16 - pulse, 28, 48 + pulse), -45, 45, fill=255, width=1)
    draw.arc((100, 16 - pulse, 128, 48 + pulse), 135, 225, fill=255, width=1)


def draw_speaking(draw: ImageDraw.ImageDraw, t: float) -> None:
    soft_eye(draw, LEFT_EYE, pupil=(0, -1), t=t)
    soft_eye(draw, RIGHT_EYE, pupil=(0, -1), t=t + 0.05)
    level = 4 + int(8 * (0.5 + 0.5 * math.sin(t * 16)))
    draw.rounded_rectangle((55, 47, 73, 47 + level), radius=5, outline=255, width=2)
    draw.line((58, 51 + level // 2, 70, 51 + level // 2), fill=255, width=1)


def draw_love(draw: ImageDraw.ImageDraw, t: float) -> None:
    heart(draw, 34, 31, 9)
    heart(draw, 92, 31, 9)
    cheek(draw, 24, 45, phase=t)
    cheek(draw, 104, 45, phase=t + 1)
    gentle_smile(draw, y=51, width=34)


def heart(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int) -> None:
    draw.ellipse((cx - s, cy - s, cx, cy), fill=255)
    draw.ellipse((cx, cy - s, cx + s, cy), fill=255)
    draw.polygon([(cx - s, cy), (cx + s, cy), (cx, cy + s + 8)], fill=255)


def draw_angry(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, LEFT_EYE, pupil=(0, 1), openness=0.72)
    eye(draw, RIGHT_EYE, pupil=(0, 1), openness=0.72)
    brow(draw, 18, 14, 52, 25)
    brow(draw, 76, 25, 110, 14)
    draw.line((52, 54, 76, 54), fill=255, width=3)


def _shift(box: tuple[int, int, int, int], dx: int, dy: int) -> tuple[int, int, int, int]:
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


EXPRESSIONS: dict[str, Expression] = {
    "neutral": Expression("neutral", draw_neutral),
    "happy": Expression("happy", draw_happy),
    "sad": Expression("sad", draw_sad),
    "sleepy": Expression("sleepy", draw_sleepy),
    "bored": Expression("bored", draw_bored),
    "surprised": Expression("surprised", draw_surprised),
    "wink": Expression("wink", draw_wink, duration=1.2),
    "thinking": Expression("thinking", draw_thinking),
    "listening": Expression("listening", draw_listening),
    "speaking": Expression("speaking", draw_speaking),
    "love": Expression("love", draw_love),
    "angry": Expression("angry", draw_angry),
}


def play_expression(device, expression: Expression, *, seconds: float | None = None) -> None:
    start = time.monotonic()
    duration = seconds if seconds is not None else expression.duration
    while time.monotonic() - start < duration:
        t = time.monotonic() - start
        image, draw = canvas()
        expression.draw(draw, t)
        device.display(image)
        time.sleep(expression.frame_delay)


def run_demo(device) -> None:
    order = [
        "neutral",
        "happy",
        "listening",
        "thinking",
        "speaking",
        "surprised",
        "wink",
        "love",
        "bored",
        "sad",
        "sleepy",
        "angry",
    ]
    while True:
        for name in order:
            play_expression(device, EXPRESSIONS[name])


def main() -> int:
    parser = argparse.ArgumentParser(description="Show Rako OLED eye expressions")
    parser.add_argument(
        "expression", nargs="?", default="demo", choices=["demo", "random", *EXPRESSIONS]
    )
    parser.add_argument("--loop", action="store_true", help="Loop a single expression")
    parser.add_argument(
        "--seconds", type=float, default=None, help="Duration for a single expression"
    )
    args = parser.parse_args()

    device = open_device()
    if args.expression == "demo":
        run_demo(device)
        return 0
    if args.expression == "random":
        while True:
            play_expression(device, EXPRESSIONS[random.choice(list(EXPRESSIONS))])

    expression = EXPRESSIONS[args.expression]
    if args.loop:
        while True:
            play_expression(device, expression, seconds=args.seconds)
    else:
        play_expression(device, expression, seconds=args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
