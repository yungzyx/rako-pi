"""OLED eye expressions for Rako.

Hardware: 128x64 SSD1306 OLED over I2C at 0x3C.

Design rule: Rako's face is eyes-only, anime-style — no mouth, no thin
decorative lines. Every mood must read from eye shape, pupil position/
shape, and openness alone, plus a couple of small filled accessories
(zzz, sparkles) where useful.

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
# Bigger, rounder, and closer together than a typical two-window OLED face —
# reads as one continuous anime-style visor instead of two separate windows.
LEFT_EYE = (21, 14, 57, 50)
RIGHT_EYE = (71, 14, 107, 50)

# Bajo esta media-altura el ojo es una ranura: se dibuja sin pupila.
_MIN_PUPIL_HALF_HEIGHT = 6

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
    pupil: tuple[float, float] = (0, 0),
    openness: float = 1.0,
) -> None:
    openness = max(0.15, min(1.0, openness))
    cx = (box[0] + box[2]) // 2
    cy = (box[1] + box[3]) // 2
    half_w = (box[2] - box[0]) // 2
    half_h = max(3, int(((box[3] - box[1]) / 2) * openness))
    eye_box = (box[0], cy - half_h, box[2], cy + half_h)
    # Radius scales with the smaller half-dimension so the eye reads as
    # round/doll-like rather than a flat pill, even as openness changes it.
    radius = max(4, min(half_w, half_h))
    draw.rounded_rectangle(eye_box, radius=radius, outline=255, fill=255)
    # Soft eyelid: trimming the top corners makes the face less stare-like.
    if openness > 0.55:
        draw.arc(
            (box[0] + 2, eye_box[1] - 6, box[2] - 2, eye_box[1] + 16), 190, 350, fill=0, width=2
        )
    # Ojo casi cerrado (parpadeo / entrecerrado fuerte): la ranura se lee
    # como una barra limpia — dibujar pupila ahí deja un punto negro raro.
    if half_h < _MIN_PUPIL_HALF_HEIGHT:
        return
    px = cx + round(pupil[0])
    py = cy + round(pupil[1])
    # Anime-style pupil: big and dominant, not a small centered dot — scales
    # with the eye's current (post-openness) height.
    pupil_r = max(2, min(half_h, int(half_h * 0.68)))
    draw.ellipse((px - pupil_r, py - pupil_r, px + pupil_r, py + pupil_r), fill=0)
    # Glossy highlight near the upper-left, like a light-source reflection.
    highlight_r = max(1, pupil_r // 3)
    hl_x = px - pupil_r * 0.4
    hl_y = py - pupil_r * 0.45
    draw.ellipse(
        (hl_x - highlight_r, hl_y - highlight_r, hl_x + highlight_r, hl_y + highlight_r),
        fill=255,
    )


def sparkle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int = 3) -> None:
    """Small four-point twinkle accent — decorative, never a mouth stand-in."""
    draw.polygon(
        [
            (cx, cy - r),
            (cx + 1, cy - 1),
            (cx + r, cy),
            (cx + 1, cy + 1),
            (cx, cy + r),
            (cx - 1, cy + 1),
            (cx - r, cy),
            (cx - 1, cy - 1),
        ],
        fill=255,
    )


# Transición de entrada: cada expresión nueva "abre los ojos" durante este
# lapso en vez de aparecer de golpe. Como cada cambio de estado relanza el
# subproceso de eyes.py (ver hardware/oled_runtime.py), esto convierte todo
# cambio de expresión en un parpadeo — el corte deja de notarse.
_ENTER_TRANSITION_SECONDS = 0.28

# Ciclo de parpadeo en reposo. Cada _BLINK_PERIOD hay un parpadeo corto; una
# de cada _DOUBLE_BLINK_EVERY veces es doble (más vivo, menos metrónomo).
_BLINK_PERIOD = 5.2
_BLINK_CLOSED_SECONDS = 0.08
_DOUBLE_BLINK_EVERY = 4
_DOUBLE_BLINK_GAP_START = 0.22
_DOUBLE_BLINK_GAP_END = 0.30


def ease_out_cubic(progress: float) -> float:
    clamped = max(0.0, min(1.0, progress))
    return 1.0 - (1.0 - clamped) ** 3


def blink_is_closed(t: float) -> bool:
    """True si en el instante `t` el párpado está abajo (parpadeo idle).

    Determinístico: mismo t → mismo frame (importante para tests y para
    que --loop no acumule deriva).
    """
    cycle_position = t % _BLINK_PERIOD
    if cycle_position < _BLINK_CLOSED_SECONDS:
        return True
    cycle_index = int(t // _BLINK_PERIOD)
    is_double_cycle = cycle_index % _DOUBLE_BLINK_EVERY == _DOUBLE_BLINK_EVERY - 1
    return is_double_cycle and _DOUBLE_BLINK_GAP_START <= cycle_position < _DOUBLE_BLINK_GAP_END


def idle_drift(t: float) -> tuple[float, float]:
    """Slow, subtle pupil wander so a still gaze doesn't read as frozen.

    Two sine terms with unrelated periods/phases trace a small
    Lissajous-like path instead of a simple back-and-forth — reads as idle
    life, not a mechanical tic. Amplitude stays under ~2px so it never
    looks like the robot is glancing away.
    """
    dx = 1.1 * math.sin(t * 0.55) + 0.5 * math.sin(t * 1.3 + 1.7)
    dy = 0.6 * math.sin(t * 0.4 + 0.6) + 0.3 * math.sin(t * 0.9 + 2.4)
    return dx, dy


def soft_eye(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    pupil: tuple[float, float] = (0, 0),
    t: float = 0.0,
    attentive: bool = False,
) -> None:
    is_blinking = blink_is_closed(t)
    openness = 0.18 if is_blinking else 0.86 + 0.06 * math.sin(t * 1.8)
    if attentive:
        openness = min(1.0, openness + 0.1)
    # No drift mid-blink: the eyelid closing should read as a clean blink,
    # not a pupil twitching as it disappears.
    drift = (0.0, 0.0) if is_blinking else idle_drift(t)
    animated_pupil = (pupil[0] + drift[0], pupil[1] + drift[1])
    eye(draw, box, pupil=animated_pupil, openness=openness)


def breathe_offset(t: float, amount: int = 2) -> int:
    return int(amount * math.sin(t * 1.7))


def closed_eye(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, tilt: int = 0) -> None:
    y = (box[1] + box[3]) // 2
    draw.line((box[0], y + tilt, box[2], y - tilt), fill=255, width=4)


def draw_neutral(draw: ImageDraw.ImageDraw, t: float) -> None:
    y = breathe_offset(t, amount=1)
    soft_eye(draw, _shift(LEFT_EYE, 0, y), t=t)
    soft_eye(draw, _shift(RIGHT_EYE, 0, y), t=t + 0.03)


def draw_happy(draw: ImageDraw.ImageDraw, t: float) -> None:
    bounce = int(2 * math.sin(t * 5))
    closed_eye(draw, _shift(LEFT_EYE, 0, bounce), tilt=-3)
    closed_eye(draw, _shift(RIGHT_EYE, 0, bounce), tilt=3)


def draw_sad(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, LEFT_EYE, pupil=(0, 5), openness=0.68)
    eye(draw, RIGHT_EYE, pupil=(0, 5), openness=0.68)


def draw_sleepy(draw: ImageDraw.ImageDraw, t: float) -> None:
    y = breathe_offset(t, amount=1)
    closed_eye(draw, _shift(LEFT_EYE, 0, y))
    closed_eye(draw, _shift(RIGHT_EYE, 0, y))
    z = int((t * 12) % 24)
    draw.text((108, 4 - z // 4), "z", fill=255)
    draw.text((117, 12 - z // 3), "Z", fill=255)


def draw_bored(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, LEFT_EYE, pupil=(-3, 2), openness=0.7)
    eye(draw, RIGHT_EYE, pupil=(-3, 2), openness=0.7)


def draw_surprised(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, (16, 8, 60, 56), pupil=(0, 0), openness=1.0)
    eye(draw, (68, 8, 112, 56), pupil=(0, 0), openness=1.0)


def draw_wink(draw: ImageDraw.ImageDraw, t: float) -> None:
    soft_eye(draw, LEFT_EYE, pupil=(3, 0), t=t, attentive=True)
    closed_eye(draw, RIGHT_EYE, tilt=2)


def draw_thinking(draw: ImageDraw.ImageDraw, t: float) -> None:
    offset = int(6 * math.sin(t * 2))
    soft_eye(draw, LEFT_EYE, pupil=(offset // 2, -1), t=t)
    soft_eye(draw, RIGHT_EYE, pupil=(offset // 2, -1), t=t + 0.08)
    for i in range(3):
        r = 1 + i
        x = 100 + i * 9
        y = 4 + int(2 * math.sin(t * 3 + i))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


def draw_listening(draw: ImageDraw.ImageDraw, t: float) -> None:
    # Sound-wave rings stay clear of the (now bigger) eyes' left/right edges.
    pulse = int(4 * (0.5 + 0.5 * math.sin(t * 8)))
    soft_eye(draw, LEFT_EYE, pupil=(-1, 0), t=t, attentive=True)
    soft_eye(draw, RIGHT_EYE, pupil=(1, 0), t=t, attentive=True)
    draw.arc((1, 22 - pulse, 17, 42 + pulse), -55, 55, fill=255, width=1)
    draw.arc((111, 22 - pulse, 127, 42 + pulse), 125, 235, fill=255, width=1)
    draw.arc((-8, 16 - pulse, 12, 48 + pulse), -45, 45, fill=255, width=1)
    draw.arc((116, 16 - pulse, 136, 48 + pulse), 135, 225, fill=255, width=1)


def draw_speaking(draw: ImageDraw.ImageDraw, t: float) -> None:
    # No mouth/waveform box — speech reads through eye movement and a pair
    # of corner sparkles that blink with the (simulated) speech rhythm.
    soft_eye(draw, LEFT_EYE, pupil=(0, -1), t=t)
    soft_eye(draw, RIGHT_EYE, pupil=(0, -1), t=t + 0.05)
    if int(t * 6) % 2 == 0:
        sparkle(draw, LEFT_EYE[0] + 3, LEFT_EYE[3] - 3, r=3)
        sparkle(draw, RIGHT_EYE[2] - 3, RIGHT_EYE[3] - 3, r=3)


def draw_love(draw: ImageDraw.ImageDraw, t: float) -> None:
    love_eye(draw, LEFT_EYE)
    love_eye(draw, RIGHT_EYE)


def love_eye(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Wide-open eye whose pupil is heart-shaped instead of round."""
    cx = (box[0] + box[2]) // 2
    cy = (box[1] + box[3]) // 2
    half_w = (box[2] - box[0]) // 2
    half_h = (box[3] - box[1]) // 2
    radius = max(4, min(half_w, half_h))
    draw.rounded_rectangle(box, radius=radius, outline=255, fill=255)
    draw.arc((box[0] + 2, box[1] - 6, box[2] - 2, box[1] + 16), 190, 350, fill=0, width=2)
    heart_size = max(3, int(half_h * 0.55))
    heart(draw, cx, cy - heart_size * 0.3, heart_size, fill=0)
    highlight_r = max(1, heart_size // 3)
    hl_x = cx - heart_size * 0.5
    hl_y = cy - heart_size * 0.9
    draw.ellipse(
        (hl_x - highlight_r, hl_y - highlight_r, hl_x + highlight_r, hl_y + highlight_r),
        fill=255,
    )


def heart(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, *, fill: int = 255) -> None:
    draw.ellipse((cx - s, cy - s, cx, cy), fill=fill)
    draw.ellipse((cx, cy - s, cx + s, cy), fill=fill)
    draw.polygon([(cx - s, cy), (cx + s, cy), (cx, cy + s * 1.5)], fill=fill)


def draw_angry(draw: ImageDraw.ImageDraw, t: float) -> None:
    eye(draw, LEFT_EYE, pupil=(0, 2), openness=0.6)
    eye(draw, RIGHT_EYE, pupil=(0, 2), openness=0.6)


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


def compose_frame(expression: Expression, t: float, *, entering: bool = False) -> Image.Image:
    """Renderiza un frame; con `entering`, superpone los párpados que se
    abren durante la ventana de transición inicial."""
    image, draw = canvas()
    expression.draw(draw, t)
    if entering and t < _ENTER_TRANSITION_SECONDS:
        _draw_enter_lids(draw, t / _ENTER_TRANSITION_SECONDS)
    return image


def _draw_enter_lids(draw: ImageDraw.ImageDraw, progress: float) -> None:
    """Párpados superior e inferior que se retiran con ease-out.

    A progress=0 cubren toda la pantalla (ojos cerrados); a progress=1 no
    queda nada. Genérico: funciona sobre cualquier expresión sin que esta
    sepa de transiciones.
    """
    opened = ease_out_cubic(progress)
    lid_height = int((HEIGHT / 2) * (1.0 - opened))
    if lid_height <= 0:
        return
    draw.rectangle((0, 0, WIDTH, lid_height), fill=0)
    draw.rectangle((0, HEIGHT - lid_height, WIDTH, HEIGHT), fill=0)


def play_expression(
    device,
    expression: Expression,
    *,
    seconds: float | None = None,
    enter: bool = True,
) -> None:
    start = time.monotonic()
    duration = seconds if seconds is not None else expression.duration
    while time.monotonic() - start < duration:
        t = time.monotonic() - start
        device.display(compose_frame(expression, t, entering=enter))
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
        # El parpadeo de entrada solo en la primera pasada — las siguientes
        # iteraciones del loop son continuidad, no un cambio de estado.
        first = True
        while True:
            play_expression(device, expression, seconds=args.seconds, enter=first)
            first = False
    else:
        play_expression(device, expression, seconds=args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
