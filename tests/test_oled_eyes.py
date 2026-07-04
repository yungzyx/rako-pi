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


def _lit_pixels(image) -> int:
    return sum(1 for pixel in image.getdata() if pixel)


def test_enter_transition_starts_closed_and_opens_fully() -> None:
    expression = eyes.EXPRESSIONS["neutral"]

    closed = eyes.compose_frame(expression, 0.0, entering=True)
    opening = eyes.compose_frame(expression, eyes._ENTER_TRANSITION_SECONDS / 2, entering=True)
    settled = eyes.compose_frame(expression, 1.0, entering=True)
    plain = eyes.compose_frame(expression, 1.0, entering=False)

    assert _lit_pixels(closed) == 0  # párpados cubren todo al inicio
    assert 0 < _lit_pixels(opening) < _lit_pixels(settled)
    assert settled.tobytes() == plain.tobytes()  # tras la ventana, no hay overlay


def test_enter_transition_is_generic_across_expressions() -> None:
    for name in ("listening", "surprised", "love", "happy"):
        expression = eyes.EXPRESSIONS[name]

        closed = eyes.compose_frame(expression, 0.0, entering=True)

        assert _lit_pixels(closed) == 0, name


def test_blink_cycle_includes_deterministic_double_blink() -> None:
    period = eyes._BLINK_PERIOD
    double_cycle_start = (eyes._DOUBLE_BLINK_EVERY - 1) * period

    assert eyes.blink_is_closed(0.04) is True  # primer parpadeo del ciclo
    assert eyes.blink_is_closed(2.0) is False
    # Segundo golpe del doble parpadeo: solo en el ciclo que corresponde.
    assert eyes.blink_is_closed(double_cycle_start + 0.25) is True
    assert eyes.blink_is_closed(period * 1 + 0.25) is False


def test_blink_slit_has_no_pupil_hole() -> None:
    # Regresión: con el ojo casi cerrado (parpadeo), la ranura debe ser una
    # barra continua — antes la pupila dejaba un punto negro en el medio.
    image, draw = eyes.canvas()
    eyes.eye(draw, eyes.LEFT_EYE, openness=0.15)

    cx = (eyes.LEFT_EYE[0] + eyes.LEFT_EYE[2]) // 2
    cy = (eyes.LEFT_EYE[1] + eyes.LEFT_EYE[3]) // 2
    assert image.getpixel((cx, cy)) == 255


def test_open_eye_still_has_pupil() -> None:
    image, draw = eyes.canvas()
    eyes.eye(draw, eyes.LEFT_EYE, openness=1.0)

    cx = (eyes.LEFT_EYE[0] + eyes.LEFT_EYE[2]) // 2
    cy = (eyes.LEFT_EYE[1] + eyes.LEFT_EYE[3]) // 2
    assert image.getpixel((cx, cy + 4)) == 0  # centro-bajo de la pupila: oscuro


def test_ease_out_cubic_is_clamped_and_monotone() -> None:
    assert eyes.ease_out_cubic(-1.0) == 0.0
    assert eyes.ease_out_cubic(0.0) == 0.0
    assert eyes.ease_out_cubic(1.0) == 1.0
    assert eyes.ease_out_cubic(2.0) == 1.0
    assert eyes.ease_out_cubic(0.3) < eyes.ease_out_cubic(0.6)
