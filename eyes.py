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

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw

WIDTH = 128
HEIGHT = 64
LEFT_EYE = (21, 18, 49, 46)
RIGHT_EYE = (79, 18, 107, 46)

FrameFn = Callable[[ImageDraw.ImageDraw, float], None]


@dataclass(frozen=True)
class Expression:
    name: str
    draw: FrameFn
    frame_delay: float = 0.08
    duration: float = 2.0


def open_device():
    serial = i2c(port=1, address=0x3C)
    return ssd1306(serial)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("1", (WIDTH, HEIGHT))
    return image, ImageDraw.Draw(image)


def eye(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, pupil: tuple[int, int] = (0, 0)) -> None:
    draw.rounded_rectangle(box, radius=10, outline=255, fill=255)
    cx = (box[0] + box[2]) // 2 + pupil[0]
    cy = (box[1] + box[3]) // 2 + pupil[1]
    draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=0)


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


def draw_neutral(draw: ImageDraw.ImageDraw, t: float) -> None:
    blink = int(t * 10) % 35 == 0
    if blink:
        closed_eye(draw, LEFT_EYE)
        closed_eye(draw, RIGHT_EYE)
    else:
        eye(draw, LEFT_EYE)
        eye(draw, RIGHT_EYE)


def draw_happy(draw: ImageDraw.ImageDraw, t: float) -> None:
    bounce = int(2 * math.sin(t * 8))
    closed_eye(draw, (21, 16 + bounce, 49, 44 + bounce), tilt=-2)
    closed_eye(draw, (79, 16 + bounce, 107, 44 + bounce), tilt=2)
    mouth(draw, "smile")


def draw_sad(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, (21, 22, 49, 47), pupil=(0, 3))
    eye(draw, (79, 22, 107, 47), pupil=(0, 3))
    brow(draw, 20, 15, 50, 22)
    brow(draw, 78, 22, 108, 15)
    mouth(draw, "sad")
    if int(t * 2) % 2 == 0:
        draw.line((50, 44, 50, 53), fill=255, width=2)


def draw_sleepy(draw: ImageDraw.ImageDraw, t: float) -> None:
    closed_eye(draw, LEFT_EYE)
    closed_eye(draw, RIGHT_EYE)
    mouth(draw, "flat")
    z = int((t * 12) % 24)
    draw.text((94, 8 - z // 3), "z", fill=255)
    draw.text((104, 18 - z // 2), "Z", fill=255)


def draw_bored(draw: ImageDraw.ImageDraw, t: float) -> None:
    draw.rounded_rectangle((21, 28, 49, 42), radius=5, fill=255)
    draw.rounded_rectangle((79, 28, 107, 42), radius=5, fill=255)
    draw.rectangle((25, 28, 45, 34), fill=0)
    draw.rectangle((83, 28, 103, 34), fill=0)
    mouth(draw, "flat")


def draw_surprised(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, (18, 12, 52, 50), pupil=(0, 0))
    eye(draw, (76, 12, 110, 50), pupil=(0, 0))
    mouth(draw, "o")


def draw_wink(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, LEFT_EYE, pupil=(2, 0))
    closed_eye(draw, RIGHT_EYE, tilt=1)
    mouth(draw, "smile")


def draw_thinking(draw: ImageDraw.ImageDraw, t: float) -> None:
    offset = int(6 * math.sin(t * 2))
    eye(draw, LEFT_EYE, pupil=(offset // 2, -1))
    eye(draw, RIGHT_EYE, pupil=(offset // 2, -1))
    for i in range(3):
        r = 1 + i
        x = 92 + i * 10
        y = 8 + int(2 * math.sin(t * 3 + i))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


def draw_listening(draw: ImageDraw.ImageDraw, t: float) -> None:
    pulse = int(4 * (0.5 + 0.5 * math.sin(t * 8)))
    eye(draw, LEFT_EYE, pupil=(0, 0))
    eye(draw, RIGHT_EYE, pupil=(0, 0))
    draw.arc((4, 20 - pulse, 20, 44 + pulse), -60, 60, fill=255, width=2)
    draw.arc((108, 20 - pulse, 124, 44 + pulse), 120, 240, fill=255, width=2)


def draw_speaking(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, LEFT_EYE, pupil=(0, -1))
    eye(draw, RIGHT_EYE, pupil=(0, -1))
    level = int(8 * (0.5 + 0.5 * math.sin(t * 18)))
    draw.rounded_rectangle((50, 48 - level // 2, 78, 56 + level // 2), radius=4, outline=255, width=2)


def draw_love(draw: ImageDraw.ImageDraw, t: float) -> None:
    heart(draw, 34, 31, 9)
    heart(draw, 92, 31, 9)
    mouth(draw, "smile")


def heart(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int) -> None:
    draw.ellipse((cx - s, cy - s, cx, cy), fill=255)
    draw.ellipse((cx, cy - s, cx + s, cy), fill=255)
    draw.polygon([(cx - s, cy), (cx + s, cy), (cx, cy + s + 8)], fill=255)


def draw_angry(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, LEFT_EYE, pupil=(0, 1))
    eye(draw, RIGHT_EYE, pupil=(0, 1))
    brow(draw, 18, 14, 52, 25)
    brow(draw, 76, 25, 110, 14)
    draw.line((52, 54, 76, 54), fill=255, width=3)


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
    parser.add_argument("expression", nargs="?", default="demo", choices=["demo", "random", *EXPRESSIONS])
    parser.add_argument("--loop", action="store_true", help="Loop a single expression")
    parser.add_argument("--seconds", type=float, default=None, help="Duration for a single expression")
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
