"""Event bus para inputs de hardware.

Modelo simple: subscribers reciben todos los eventos. Excepciones en un
callback NO deben afectar a los demás — el handler del botón de pánico
no puede silenciarse por un bug en otro suscriptor.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from hardware.types import HardwareEvent

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Subscription:
    id: int


@runtime_checkable
class HardwareEventBus(Protocol):
    def subscribe(self, callback: Callable[[HardwareEvent], None]) -> Subscription: ...
    def unsubscribe(self, subscription: Subscription) -> None: ...


class InMemoryHardwareEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[int, Callable[[HardwareEvent], None]] = {}
        self._next_id = 0

    def subscribe(self, callback: Callable[[HardwareEvent], None]) -> Subscription:
        sub_id = self._next_id
        self._next_id += 1
        self._subscribers[sub_id] = callback
        return Subscription(id=sub_id)

    def unsubscribe(self, subscription: Subscription) -> None:
        self.unsubscribe_id(subscription.id)

    def unsubscribe_id(self, sub_id: int) -> None:
        self._subscribers.pop(sub_id, None)

    def emit(self, event: HardwareEvent) -> None:
        # Aislamos cada callback para que un fallo no propague al resto.
        for sub_id, cb in list(self._subscribers.items()):
            try:
                cb(event)
            except Exception:
                _log.exception("hardware event subscriber %s raised", sub_id)
