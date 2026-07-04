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


def test_neutral_expression_shows_both_eyes() -> None:
    image = _render("neutral", t=0.4)

    left_region = image.crop(eyes.LEFT_EYE)
    right_region = image.crop(eyes.RIGHT_EYE)
    assert left_region.getbbox() is not None
    assert right_region.getbbox() is not None


def test_no_mouth_drawing_helpers_exist() -> None:
    # Rako's face is eyes-only (anime-style) — no mouth. These helpers must
    # not exist so nobody can wire a mouth back into an expression later.
    assert not hasattr(eyes, "mouth")
    assert not hasattr(eyes, "gentle_smile")
