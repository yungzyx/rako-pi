from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database
from productivity.crisis_gate import has_recent_crisis_event
from safety.types import CrisisLevel, CrisisReason, CrisisSignal


def _now() -> datetime:
    return datetime(2026, 6, 20, 14, 0, tzinfo=UTC)


def test_has_recent_crisis_event_is_false_with_empty_journal(db_conn) -> None:
    db = Database(db_conn)

    assert has_recent_crisis_event(db, now=_now()) is False


def test_has_recent_crisis_event_is_true_within_lookback(db_conn) -> None:
    db = Database(db_conn)
    db.crisis_journal.record(
        CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.PANIC_BUTTON_PHYSICAL,),
            detected_at=_now() - timedelta(hours=2),
        )
    )

    assert has_recent_crisis_event(db, now=_now(), lookback=timedelta(hours=24)) is True


def test_has_recent_crisis_event_is_false_outside_lookback(db_conn) -> None:
    db = Database(db_conn)
    db.crisis_journal.record(
        CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.PANIC_BUTTON_PHYSICAL,),
            detected_at=_now() - timedelta(hours=30),
        )
    )

    assert has_recent_crisis_event(db, now=_now(), lookback=timedelta(hours=24)) is False
