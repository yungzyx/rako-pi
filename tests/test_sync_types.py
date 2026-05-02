"""Tests de los tipos del módulo sync."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sync.types import SyncEvent, SyncEventKind

UTC = timezone.utc


def test_sync_event_kind_only_includes_non_sensitive_events() -> None:
    # Allow-list explícita: nada de "EMOTIONAL_STATE", "TRANSCRIPT_LOGGED",
    # etc. Si alguien agrega un kind sensible, este test falla.
    allowed = {k.name for k in SyncEventKind}

    assert "EMOTIONAL_STATE" not in allowed
    assert "TRANSCRIPT_LOGGED" not in allowed
    assert "AUDIO_RECORDED" not in allowed
    # Allowed: agregados de progreso y eventos UI.
    assert "TASK_COMPLETED" in allowed
    assert "PANIC_BUTTON" in allowed
    assert "ACHIEVEMENT_EARNED" in allowed
    assert "LEVEL_UP" in allowed


def test_sync_event_is_immutable() -> None:
    event = SyncEvent(
        id="a",
        kind=SyncEventKind.TASK_COMPLETED,
        occurred_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        payload={"task_count": 3},
    )

    with pytest.raises(Exception):
        event.id = "b"  # type: ignore[misc]


def test_sync_event_construction_basic() -> None:
    event = SyncEvent(
        id="evt_1",
        kind=SyncEventKind.PANIC_BUTTON,
        occurred_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        payload={"source": "physical"},
    )

    assert event.id == "evt_1"
    assert event.kind is SyncEventKind.PANIC_BUTTON
    assert event.payload["source"] == "physical"
