"""Controlador de servos (cabeza, orejas).

Rango limitado a [-90, 90] grados para evitar daño mecánico y ruido
excesivo. Movimientos suaves se gestionan en una capa superior (la
capa de animación), no aquí.
"""

from __future__ import annotations

from typing import Final, Protocol, runtime_checkable

_ANGLE_MIN: Final[float] = -90.0
_ANGLE_MAX: Final[float] = 90.0


@runtime_checkable
class ServoController(Protocol):
    def set_head_angle(self, degrees: float) -> None: ...
    def set_ear_angle(self, degrees: float) -> None: ...
    def reset(self) -> None: ...


class FakeServoController:
    def __init__(self) -> None:
        self.head_angle: float = 0.0
        self.ear_angle: float = 0.0

    def set_head_angle(self, degrees: float) -> None:
        _validate(degrees)
        self.head_angle = degrees

    def set_ear_angle(self, degrees: float) -> None:
        _validate(degrees)
        self.ear_angle = degrees

    def reset(self) -> None:
        self.head_angle = 0.0
        self.ear_angle = 0.0


def _validate(degrees: float) -> None:
    if not _ANGLE_MIN <= degrees <= _ANGLE_MAX:
        raise ValueError(f"angle out of range [{_ANGLE_MIN}, {_ANGLE_MAX}]: {degrees}")
