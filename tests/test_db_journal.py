"""Tests para el CrisisJournal — registro privado de eventos de crisis."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from db.connection import open_connection
from db.journal import CrisisJournal, CrisisJournalEntry
from db.schema import create_all
from safety.types import CrisisLevel, CrisisReason, CrisisSignal

UTC = UTC


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _signal(*reasons: CrisisReason, level: CrisisLevel = CrisisLevel.CRISIS) -> CrisisSignal:
    return CrisisSignal(level=level, reasons=reasons, detected_at=_now())


@pytest.fixture
def journal() -> Iterator[CrisisJournal]:
    conn = open_connection(":memory:")
    try:
        create_all(conn)
        yield CrisisJournal(conn)
    finally:
        conn.close()


def test_record_persists_signal(journal: CrisisJournal) -> None:
    signal = _signal(CrisisReason.PANIC_BUTTON_PHYSICAL)

    journal.record(signal)

    entries = journal.list_recent(limit=10)
    assert len(entries) == 1
    assert isinstance(entries[0], CrisisJournalEntry)
    assert entries[0].level == "CRISIS"
    assert entries[0].reasons == ("PANIC_BUTTON_PHYSICAL",)
    assert entries[0].detected_at == _now()


def test_record_preserves_reason_order(journal: CrisisJournal) -> None:
    signal = _signal(
        CrisisReason.PANIC_BUTTON_PHYSICAL,
        CrisisReason.KEYWORDS_IDEATION,
        CrisisReason.SUSTAINED_EMOTIONAL_EXTREME,
    )

    journal.record(signal)

    entries = journal.list_recent()
    assert entries[0].reasons == (
        "PANIC_BUTTON_PHYSICAL",
        "KEYWORDS_IDEATION",
        "SUSTAINED_EMOTIONAL_EXTREME",
    )


def test_list_recent_orders_newest_first(journal: CrisisJournal) -> None:
    a = CrisisSignal(
        CrisisLevel.CRISIS, (CrisisReason.PANIC_BUTTON_APP,), _now() - timedelta(hours=1)
    )
    b = CrisisSignal(CrisisLevel.CRISIS, (CrisisReason.KEYWORDS_IDEATION,), _now())

    journal.record(a)
    journal.record(b)

    entries = journal.list_recent()
    assert entries[0].reasons == ("KEYWORDS_IDEATION",)
    assert entries[1].reasons == ("PANIC_BUTTON_APP",)


def test_list_recent_respects_limit(journal: CrisisJournal) -> None:
    for i in range(5):
        s = CrisisSignal(
            CrisisLevel.CRISIS,
            (CrisisReason.PANIC_BUTTON_APP,),
            _now() - timedelta(minutes=i),
        )
        journal.record(s)

    entries = journal.list_recent(limit=2)
    assert len(entries) == 2


def test_record_rejects_non_crisis_signal(journal: CrisisJournal) -> None:
    signal = _signal(level=CrisisLevel.NONE)

    with pytest.raises(ValueError):
        journal.record(signal)


def test_purge_deletes_all_entries(journal: CrisisJournal) -> None:
    journal.record(_signal(CrisisReason.PANIC_BUTTON_PHYSICAL))
    journal.record(_signal(CrisisReason.KEYWORDS_IDEATION))

    deleted = journal.purge()

    assert deleted == 2
    assert journal.list_recent() == []


def test_record_can_attach_response_id(journal: CrisisJournal) -> None:
    signal = _signal(CrisisReason.KEYWORDS_IDEATION)

    journal.record(signal, response_id="ideation", contact_notified=True)

    entry = journal.list_recent()[0]
    assert entry.response_id == "ideation"
    assert entry.contact_notified is True


def test_record_defaults_when_no_response_metadata(journal: CrisisJournal) -> None:
    journal.record(_signal(CrisisReason.PANIC_BUTTON_PHYSICAL))

    entry = journal.list_recent()[0]
    assert entry.response_id is None
    assert entry.contact_notified is False


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_list_recent_rejects_non_positive_limit(journal: CrisisJournal, limit: int) -> None:
    with pytest.raises(ValueError):
        journal.list_recent(limit=limit)
