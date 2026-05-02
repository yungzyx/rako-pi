"""Tests del SyncQueue sobre la tabla sync_queue."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sync.queue import SyncQueue
from sync.types import SyncEvent, SyncEventKind

UTC = UTC


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _event(id_: str = "e1", kind: SyncEventKind = SyncEventKind.TASK_COMPLETED) -> SyncEvent:
    return SyncEvent(
        id=id_,
        kind=kind,
        occurred_at=_now(),
        payload={"count": 1},
    )


def test_enqueue_persists_event(db_conn) -> None:
    queue = SyncQueue(db_conn)
    event = _event()

    queue.enqueue(event)

    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0].event.id == "e1"


def test_enqueue_strips_pii_from_payload(db_conn) -> None:
    queue = SyncQueue(db_conn)
    bad = SyncEvent(
        id="x",
        kind=SyncEventKind.TASK_COMPLETED,
        occurred_at=_now(),
        payload={"transcript": "secreto", "count": 5},
    )

    queue.enqueue(bad)

    pending = queue.list_pending()
    assert "transcript" not in pending[0].event.payload
    assert pending[0].event.payload["count"] == 5


def test_list_pending_orders_oldest_first(db_conn) -> None:
    queue = SyncQueue(db_conn)
    queue.enqueue(_event(id_="first"))
    queue.enqueue(_event(id_="second"))
    queue.enqueue(_event(id_="third"))

    pending = queue.list_pending()

    assert [p.event.id for p in pending] == ["first", "second", "third"]


def test_mark_succeeded_removes_event(db_conn) -> None:
    queue = SyncQueue(db_conn)
    queue.enqueue(_event(id_="a"))
    queue.enqueue(_event(id_="b"))

    [first, _] = queue.list_pending()
    queue.mark_succeeded(first)

    remaining = queue.list_pending()
    assert {p.event.id for p in remaining} == {"b"}


def test_mark_failed_increments_attempts(db_conn) -> None:
    queue = SyncQueue(db_conn)
    queue.enqueue(_event(id_="a"))
    [pending] = queue.list_pending()

    queue.mark_failed(pending, error="network down")

    [after] = queue.list_pending()
    assert after.attempts == 1
    assert after.last_error == "network down"


def test_dead_letter_after_max_attempts(db_conn) -> None:
    queue = SyncQueue(db_conn, max_attempts=3)
    queue.enqueue(_event(id_="a"))

    for _ in range(4):
        pending = queue.list_pending()
        if not pending:
            break
        queue.mark_failed(pending[0], error="x")

    # Después de superar max_attempts el evento ya no aparece en pending.
    assert queue.list_pending() == []


def test_purge_all(db_conn) -> None:
    queue = SyncQueue(db_conn)
    queue.enqueue(_event(id_="a"))
    queue.enqueue(_event(id_="b"))

    deleted = queue.purge_all()

    assert deleted == 2
    assert queue.list_pending() == []


def test_list_pending_respects_limit(db_conn) -> None:
    queue = SyncQueue(db_conn)
    for i in range(5):
        queue.enqueue(_event(id_=f"e{i}"))

    pending = queue.list_pending(limit=3)

    assert len(pending) == 3


def test_list_pending_rejects_non_positive_limit(db_conn) -> None:
    queue = SyncQueue(db_conn)

    for bad in (0, -1):
        with pytest.raises(ValueError):
            queue.list_pending(limit=bad)
