"""Sensores PIR y táctil sobre gpiozero."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from hardware.event_bus import HardwareEventBus
from hardware.types import HardwareEvent, HardwareEventKind


class GpioZeroPIR:
    def __init__(
        self,
        *,
        motion_sensor: Any,
        bus: HardwareEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._bus = bus
        self._now = now
        motion_sensor.when_motion = lambda: self._emit()

    def _emit(self) -> None:
        self._bus.emit(  # type: ignore[attr-defined]
            HardwareEvent(kind=HardwareEventKind.PIR_MOTION, at=self._now())
        )


class GpioZeroTouch:
    def __init__(
        self,
        *,
        touch_input: Any,
        bus: HardwareEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._bus = bus
        self._now = now
        touch_input.when_pressed = lambda: self._emit()

    def _emit(self) -> None:
        self._bus.emit(  # type: ignore[attr-defined]
            HardwareEvent(kind=HardwareEventKind.TOUCH, at=self._now())
        )


def create_pi_pir(  # pragma: no cover - Pi only
    *, pin: int, bus: HardwareEventBus, now: Callable[[], datetime]
) -> GpioZeroPIR:
    from gpiozero import MotionSensor  # type: ignore[import-not-found]

    return GpioZeroPIR(motion_sensor=MotionSensor(pin), bus=bus, now=now)


def create_pi_touch(  # pragma: no cover - Pi only
    *, pin: int, bus: HardwareEventBus, now: Callable[[], datetime]
) -> GpioZeroTouch:
    from gpiozero import Button  # type: ignore[import-not-found]

    return GpioZeroTouch(touch_input=Button(pin), bus=bus, now=now)
