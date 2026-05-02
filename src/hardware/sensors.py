"""Sensores: PIR (presencia) y táctil capacitivo.

Mismo patrón que `buttons.py`: emiten `HardwareEvent` al bus. La impl
real conecta a `gpiozero.MotionSensor` y `gpiozero.Button` (capacitivo
expuesto como input digital).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from hardware.event_bus import HardwareEventBus
from hardware.types import HardwareEvent, HardwareEventKind


class FakePIR:
    def __init__(
        self,
        bus: HardwareEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._bus = bus
        self._now = now

    def trigger(self) -> None:
        self._bus.emit(HardwareEvent(kind=HardwareEventKind.PIR_MOTION, at=self._now()))  # type: ignore[attr-defined]


class FakeTouch:
    def __init__(
        self,
        bus: HardwareEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._bus = bus
        self._now = now

    def tap(self) -> None:
        self._bus.emit(HardwareEvent(kind=HardwareEventKind.TOUCH, at=self._now()))  # type: ignore[attr-defined]
