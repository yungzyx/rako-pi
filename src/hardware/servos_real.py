"""Servos sobre gpiozero (cabeza + orejas)."""

from __future__ import annotations

from typing import Any, Final

_ANGLE_MIN: Final[float] = -90.0
_ANGLE_MAX: Final[float] = 90.0


def _angle_to_value(degrees: float) -> float:
    """Mapea grados [-90, 90] al rango de gpiozero.Servo.value [-1, 1]."""
    if not _ANGLE_MIN <= degrees <= _ANGLE_MAX:
        raise ValueError(f"angle out of range [{_ANGLE_MIN}, {_ANGLE_MAX}]: {degrees}")
    return degrees / _ANGLE_MAX


class GpioZeroServos:
    def __init__(self, *, head_servo: Any, ear_servo: Any) -> None:
        self._head = head_servo
        self._ear = ear_servo

    def set_head_angle(self, degrees: float) -> None:
        self._head.value = _angle_to_value(degrees)

    def set_ear_angle(self, degrees: float) -> None:
        self._ear.value = _angle_to_value(degrees)

    def reset(self) -> None:
        self._head.value = 0.0
        self._ear.value = 0.0


def create_pi_servos(  # pragma: no cover - Pi only
    *, head_pin: int, ear_pin: int
) -> GpioZeroServos:
    from gpiozero import Servo  # type: ignore[import-not-found]

    return GpioZeroServos(head_servo=Servo(head_pin), ear_servo=Servo(ear_pin))
