from __future__ import annotations

import eyes


def _render(expression: str, t: float = 0.4):
    image, draw = eyes.canvas()
    eyes.EXPRESSIONS[expression].draw(draw, t)
    return image


def test_all_eye_expressions_render_visible_pixels() -> None:
    for name in eyes.EXPRESSIONS:
        image = _render(name)

        assert image.getbbox() is not None, name


def test_core_eye_expressions_animate_between_frames() -> None:
    for name in ("listening", "thinking", "speaking", "happy"):
        first = _render(name, t=0.2)
        second = _render(name, t=0.9)

        assert first.tobytes() != second.tobytes(), name


def test_neutral_expression_has_gentle_smile_and_eyes() -> None:
    image = _render("neutral", t=0.4)

    assert image.getpixel((30, 32)) == 255
    assert image.getpixel((64, 60)) == 255
