"""Tests del SyncCoordinator — queue + client + retry."""

from __future__ import annotations

from datetime import UTC, datetime

from sync.coordinator import SyncCoordinator
from sync.firebase_client import FakeFirebaseClient
from sync.queue import SyncQueue
from sync.types import SyncEvent, SyncEventKind

UTC = UTC


def _event(id_: str = "e1") -> SyncEvent:
    return SyncEvent(
        id=id_,
        kind=SyncEventKind.TASK_COMPLETED,
        occurred_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        payload={"count": 1},
    )


def test_drain_sends_all_pending_when_client_works(db_conn) -> None:
    queue = SyncQueue(db_conn)
    client = FakeFirebaseClient()
    coord = SyncCoordinator(queue=queue, client=client)

    coord.enqueue(_event(id_="a"))
    coord.enqueue(_event(id_="b"))
    coord.enqueue(_event(id_="c"))

    sent = coord.drain()

    assert sent == 3
    assert {e.id for e in client.sent} == {"a", "b", "c"}
    assert queue.list_pending() == []


def test_drain_stops_on_first_failure(db_conn) -> None:
    queue = SyncQueue(db_conn)
    client = FakeFirebaseClient(fail_first_n=99)  # siempre falla
    coord = SyncCoordinator(queue=queue, client=client)

    coord.enqueue(_event(id_="a"))
    coord.enqueue(_event(id_="b"))

    sent = coord.drain()

    assert sent == 0
    # Ambos siguen en cola, el primero con attempts=1 (no se intentaron los demás).
    pending = queue.list_pending()
    assert len(pending) == 2
    assert pending[0].attempts == 1
    assert pending[1].attempts == 0


def test_drain_recovers_after_transient_failure(db_conn) -> None:
    queue = SyncQueue(db_conn)
    client = FakeFirebaseClient(fail_first_n=1)
    coord = SyncCoordinator(queue=queue, client=client)

    coord.enqueue(_event(id_="a"))

    # Primer drain: el client falla, evento queda en cola.
    sent = coord.drain()
    assert sent == 0
    assert queue.list_pending()[0].attempts == 1

    # Segundo drain: recupera.
    sent = coord.drain()
    assert sent == 1
    assert queue.list_pending() == []


def test_drain_skips_when_client_unavailable(db_conn) -> None:
    queue = SyncQueue(db_conn)
    client = FakeFirebaseClient(available=False)
    coord = SyncCoordinator(queue=queue, client=client)

    coord.enqueue(_event(id_="a"))

    sent = coord.drain()

    assert sent == 0
    # No se incrementa attempts si is_available() retornó False.
    assert queue.list_pending()[0].attempts == 0


def test_enqueue_sanitizes_pii(db_conn) -> None:
    queue = SyncQueue(db_conn)
    client = FakeFirebaseClient()
    coord = SyncCoordinator(queue=queue, client=client)

    bad = SyncEvent(
        id="x",
        kind=SyncEventKind.TASK_COMPLETED,
        occurred_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        payload={"transcript": "secreto", "count": 1},
    )

    coord.enqueue(bad)
    coord.drain()

    assert client.sent[0].payload == {"count": 1}
