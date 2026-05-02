"""Tests del servo controller (cabeza + orejas)."""

from __future__ import annotations

import pytest

from hardware.servos import FakeServoController, ServoController


def test_fake_satisfies_protocol() -> None:
    servo: ServoController = FakeServoController()
    assert hasattr(servo, "set_head_angle")
    assert hasattr(servo, "set_ear_angle")
    assert hasattr(servo, "reset")


def test_set_head_angle_records_value() -> None:
    servo = FakeServoController()

    servo.set_head_angle(15.0)

    assert servo.head_angle == 15.0


def test_set_ear_angle_records_value() -> None:
    servo = FakeServoController()

    servo.set_ear_angle(-20.0)

    assert servo.ear_angle == -20.0


def test_reset_returns_to_zero() -> None:
    servo = FakeServoController()
    servo.set_head_angle(45.0)
    servo.set_ear_angle(30.0)

    servo.reset()

    assert servo.head_angle == 0.0
    assert servo.ear_angle == 0.0


@pytest.mark.parametrize("angle", [-91.0, 91.0, 180.0, -200.0])
def test_set_head_angle_rejects_out_of_range(angle: float) -> None:
    servo = FakeServoController()

    with pytest.raises(ValueError):
        servo.set_head_angle(angle)


@pytest.mark.parametrize("angle", [-91.0, 91.0])
def test_set_ear_angle_rejects_out_of_range(angle: float) -> None:
    servo = FakeServoController()

    with pytest.raises(ValueError):
        servo.set_ear_angle(angle)
