"""Tests del GpioZeroServos (wrapper inyectable)."""

from __future__ import annotations

import pytest

from hardware.servos_real import GpioZeroServos


class _FakeServo:
    """Mimic gpiozero.Servo: .value in [-1, 1] mapping to [-90, 90]."""

    def __init__(self) -> None:
        self.value: float = 0.0
        self.detach_calls = 0

    def detach(self) -> None:
        self.detach_calls += 1


def test_set_head_angle_maps_to_value_range() -> None:
    head = _FakeServo()
    ear = _FakeServo()
    servos = GpioZeroServos(head_servo=head, ear_servo=ear)

    servos.set_head_angle(45.0)

    # 45° debería mapear a +0.5 en el rango [-1, 1].
    assert head.value == pytest.approx(0.5)


def test_set_ear_angle_maps_to_value_range() -> None:
    head = _FakeServo()
    ear = _FakeServo()
    servos = GpioZeroServos(head_servo=head, ear_servo=ear)

    servos.set_ear_angle(-90.0)

    assert ear.value == pytest.approx(-1.0)


def test_reset_returns_both_to_neutral() -> None:
    head = _FakeServo()
    ear = _FakeServo()
    servos = GpioZeroServos(head_servo=head, ear_servo=ear)
    servos.set_head_angle(45.0)
    servos.set_ear_angle(30.0)

    servos.reset()

    assert head.value == 0.0
    assert ear.value == 0.0


@pytest.mark.parametrize("angle", [-91.0, 91.0, 180.0])
def test_set_head_angle_rejects_out_of_range(angle: float) -> None:
    head = _FakeServo()
    ear = _FakeServo()
    servos = GpioZeroServos(head_servo=head, ear_servo=ear)

    with pytest.raises(ValueError):
        servos.set_head_angle(angle)


def test_set_ear_angle_rejects_out_of_range() -> None:
    head = _FakeServo()
    ear = _FakeServo()
    servos = GpioZeroServos(head_servo=head, ear_servo=ear)

    with pytest.raises(ValueError):
        servos.set_ear_angle(91.0)
