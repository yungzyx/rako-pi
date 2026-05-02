"""Tests del FirebaseClient (Protocol + fake)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sync.firebase_client import FakeFirebaseClient, FirebaseClient
from sync.types import SyncEvent, SyncEventKind

UTC = timezone.utc


def _event() -> SyncEvent:
    return SyncEvent(
        id="evt",
        kind=SyncEventKind.TASK_COMPLETED,
        occurred_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        payload={"count": 1},
    )


def test_fake_satisfies_protocol() -> None:
    client: FirebaseClient = FakeFirebaseClient()
    assert hasattr(client, "send")


def test_fake_records_sent_events() -> None:
    client = FakeFirebaseClient()

    client.send(_event())

    assert len(client.sent) == 1
    assert client.sent[0].id == "evt"


def test_fake_can_simulate_failures() -> None:
    client = FakeFirebaseClient(fail_first_n=2)

    with pytest.raises(ConnectionError):
        client.send(_event())
    with pytest.raises(ConnectionError):
        client.send(_event())
    # Tercer intento ya no falla.
    client.send(_event())

    assert len(client.sent) == 1


def test_fake_is_available_when_not_disabled() -> None:
    client = FakeFirebaseClient()

    assert client.is_available() is True


def test_fake_can_be_disabled_to_simulate_offline() -> None:
    client = FakeFirebaseClient(available=False)

    assert client.is_available() is False
