"""Tests del EmotionalStateRepository — alimenta al detector de crisis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from db.repositories import EmotionalStateRepository
from db.types import EmotionalStateRecord
from emotion.types import EmotionalVector
from safety.types import EmotionalSample

UTC = UTC


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _record(
    *,
    id: str = "e1",
    at: datetime | None = None,
    valence: float = -0.2,
    arousal: float = 0.4,
    dominance: float = 0.5,
    trigger_event: str | None = None,
    confidence: float = 0.9,
) -> EmotionalStateRecord:
    return EmotionalStateRecord(
        id=id,
        at=at or _now(),
        vector=EmotionalVector(valence=valence, arousal=arousal, dominance=dominance),
        trigger_event=trigger_event,
        confidence=confidence,
    )


def test_append_round_trip(db_conn) -> None:
    repo = EmotionalStateRepository(db_conn)
    record = _record(trigger_event="user_responded")

    saved = repo.append(record)

    assert saved == record
    assert repo.list_in_window(end=_now(), lookback=timedelta(minutes=5))[0] == record


def test_list_in_window_filters_outside_window(db_conn) -> None:
    repo = EmotionalStateRepository(db_conn)
    repo.append(_record(id="recent", at=_now() - timedelta(minutes=2)))
    repo.append(_record(id="old", at=_now() - timedelta(minutes=30)))

    in_window = repo.list_in_window(end=_now(), lookback=timedelta(minutes=10))

    assert {r.id for r in in_window} == {"recent"}


def test_list_in_window_orders_oldest_first(db_conn) -> None:
    repo = EmotionalStateRepository(db_conn)
    repo.append(_record(id="t2", at=_now() - timedelta(minutes=2)))
    repo.append(_record(id="t6", at=_now() - timedelta(minutes=6)))
    repo.append(_record(id="t4", at=_now() - timedelta(minutes=4)))

    ordered = repo.list_in_window(end=_now(), lookback=timedelta(minutes=10))

    assert [r.id for r in ordered] == ["t6", "t4", "t2"]


def test_list_samples_in_window_returns_emotional_samples(db_conn) -> None:
    # Esto es lo que el detector consume directamente.
    repo = EmotionalStateRepository(db_conn)
    repo.append(_record(id="a", at=_now() - timedelta(minutes=2), valence=-0.8, arousal=0.8))

    samples = repo.list_samples_in_window(end=_now(), lookback=timedelta(minutes=5))

    assert len(samples) == 1
    assert isinstance(samples[0], EmotionalSample)
    assert samples[0].vector.valence == -0.8


def test_list_in_window_rejects_negative_lookback(db_conn) -> None:
    repo = EmotionalStateRepository(db_conn)

    with pytest.raises(ValueError):
        repo.list_in_window(end=_now(), lookback=timedelta(minutes=-1))


def test_purge_all(db_conn) -> None:
    repo = EmotionalStateRepository(db_conn)
    repo.append(_record(id="a"))
    repo.append(_record(id="b"))

    deleted = repo.purge_all()

    assert deleted == 2
