"""Botones físicos sobre gpiozero (wrapper inyectable + factory Pi)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from hardware.event_bus import HardwareEventBus
from hardware.types import HardwareEvent, HardwareEventKind


class GpioZeroButtons:
    def __init__(
        self,
        *,
        panic_button: Any,
        emergency_button: Any,
        bus: HardwareEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._bus = bus
        self._now = now
        panic_button.when_pressed = lambda: self._emit(HardwareEventKind.BUTTON_PANIC)
        emergency_button.when_pressed = lambda: self._emit(HardwareEventKind.BUTTON_EMERGENCY)

    def _emit(self, kind: HardwareEventKind) -> None:
        self._bus.emit(HardwareEvent(kind=kind, at=self._now()))  # type: ignore[attr-defined]


def create_pi_buttons(  # pragma: no cover - Pi only
    *,
    panic_pin: int,
    emergency_pin: int,
    bus: HardwareEventBus,
    now: Callable[[], datetime],
) -> GpioZeroButtons:
    from gpiozero import Button  # type: ignore[import-not-found]

    return GpioZeroButtons(
        panic_button=Button(panic_pin),
        emergency_button=Button(emergency_pin),
        bus=bus,
        now=now,
    )
