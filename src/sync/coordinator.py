"""SyncCoordinator — orquesta queue + client con stop-on-first-failure.

Heurística: si un send falla, asumimos red caída y NO seguimos
intentando los demás eventos (evita gastar retries cuando todos van a
fallar). El siguiente `drain()` reintenta desde el principio.

Si el cliente reporta `is_available()=False` (e.g. flag offline,
reglas de Firebase no desplegadas), saltamos el drain entero sin
incrementar `attempts` — no queremos consumir cuota de reintentos
por algo que sabemos que va a fallar.
"""

from __future__ import annotations

from sync.firebase_client import FirebaseClient
from sync.queue import SyncQueue
from sync.types import SyncEvent


class SyncCoordinator:
    def __init__(self, *, queue: SyncQueue, client: FirebaseClient) -> None:
        self._queue = queue
        self._client = client

    def enqueue(self, event: SyncEvent) -> None:
        self._queue.enqueue(event)

    def drain(self) -> int:
        if not self._client.is_available():
            return 0

        sent = 0
        for queued in self._queue.list_pending():
            try:
                self._client.send(queued.event)
            except Exception as exc:
                self._queue.mark_failed(queued, error=str(exc))
                break
            self._queue.mark_succeeded(queued)
            sent += 1
        return sent
