"""Botones físicos: pánico y emergencia.

Emiten `HardwareEvent` al `HardwareEventBus`. La implementación real
(via `gpiozero.Button`) se conecta vía un suscriptor que llama
`_emit` cuando el GPIO dispara su callback `when_pressed`.

`FakeButtons` reproduce el comportamiento en memoria para tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from hardware.event_bus import HardwareEventBus
from hardware.types import HardwareEvent, HardwareEventKind


class FakeButtons:
    def __init__(
        self,
        bus: HardwareEventBus,
        now: Callable[[], datetime],
    ) -> None:
        self._bus = bus
        self._now = now

    def press_panic(self) -> None:
        self._emit(HardwareEventKind.BUTTON_PANIC)

    def press_emergency(self) -> None:
        self._emit(HardwareEventKind.BUTTON_EMERGENCY)

    def _emit(self, kind: HardwareEventKind) -> None:
        self._bus.emit(HardwareEvent(kind=kind, at=self._now()))  # type: ignore[attr-defined]
