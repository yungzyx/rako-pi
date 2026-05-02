"""Tests del AchievementRepository."""

from __future__ import annotations

from datetime import datetime, timezone

from db.repositories import AchievementRepository
from db.types import Achievement

UTC = timezone.utc


def _achievement(*, id: str = "a1", type: str = "first_task", level: int = 1) -> Achievement:
    return Achievement(
        id=id,
        type=type,
        earned_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        robot_level_after=level,
    )


def test_record_persists_achievement(db_conn) -> None:
    repo = AchievementRepository(db_conn)
    a = _achievement()

    saved = repo.record(a)

    assert saved == a
    assert repo.list_all() == [a]


def test_list_all_orders_by_earned_at_descending(db_conn) -> None:
    repo = AchievementRepository(db_conn)
    a = Achievement(id="a", type="t", earned_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC), robot_level_after=1)
    b = Achievement(id="b", type="t", earned_at=datetime(2026, 5, 2, 18, 0, tzinfo=UTC), robot_level_after=2)
    repo.record(a)
    repo.record(b)

    all_ = repo.list_all()

    assert [x.id for x in all_] == ["b", "a"]


def test_purge_all(db_conn) -> None:
    repo = AchievementRepository(db_conn)
    repo.record(_achievement(id="a"))
    repo.record(_achievement(id="b"))

    deleted = repo.purge_all()

    assert deleted == 2
