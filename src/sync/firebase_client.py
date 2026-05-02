"""FirebaseClient — Protocol + fake.

La impl real (`firebase_admin`) lazy-importa al provisionar la Pi.
`send(event)` debe sanitizar el payload una segunda vez antes del
wire (defense-in-depth, aunque la cola ya sanitiza).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sync.types import SyncEvent


@runtime_checkable
class FirebaseClient(Protocol):
    def send(self, event: SyncEvent) -> None: ...
    def is_available(self) -> bool: ...


class FakeFirebaseClient:
    def __init__(
        self,
        *,
        fail_first_n: int = 0,
        available: bool = True,
    ) -> None:
        self.sent: list[SyncEvent] = []
        self._fail_remaining = fail_first_n
        self._available = available

    def send(self, event: SyncEvent) -> None:
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise ConnectionError("simulated network failure")
        self.sent.append(event)

    def is_available(self) -> bool:
        return self._available
