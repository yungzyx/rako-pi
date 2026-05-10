from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from productivity.countdown import CountdownConfig, CountdownRunner
from productivity.focus import FocusSessionStatus, create_focus_task, start_focus_session


def test_countdown_config_rejects_non_positive_tick() -> None:
    with pytest.raises(ValueError):
        CountdownConfig(tick_seconds=0)


def test_countdown_runner_ticks_until_done() -> None:
    start = datetime(2026, 5, 10, 18, 0, tzinfo=UTC)
    task = create_focus_task("leer", start)
    session = start_focus_session(task, start, minutes=2)
    times = iter(
        [
            start,
            start + timedelta(minutes=1),
            start + timedelta(minutes=2),
        ]
    )
    ticks: list[timedelta] = []
    sleeps: list[float] = []

    runner = CountdownRunner(
        clock=lambda: next(times),
        sleeper=sleeps.append,
        config=CountdownConfig(tick_seconds=60),
    )

    completed = runner.run(session, on_tick=ticks.append)

    assert completed.status is FocusSessionStatus.COMPLETED
    assert ticks == [timedelta(minutes=2), timedelta(minutes=1), timedelta()]
    assert sleeps == [60, 60]


def test_countdown_runner_calls_done_callback() -> None:
    start = datetime(2026, 5, 10, 18, 0, tzinfo=UTC)
    task = create_focus_task("leer", start)
    session = start_focus_session(task, start, minutes=1)
    completed_sessions = []

    runner = CountdownRunner(
        clock=lambda: start + timedelta(minutes=1),
        sleeper=lambda _: None,
    )

    completed = runner.run(session, on_done=completed_sessions.append)

    assert completed_sessions == [completed]
