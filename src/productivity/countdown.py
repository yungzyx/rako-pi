"""Countdown runtime for focus sessions.

Small synchronous runner. It is intentionally dependency-light so it can be used
from scripts today and replaced by a systemd/service loop later.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from productivity.focus import FocusSession

TickCallback = Callable[[timedelta], None]
DoneCallback = Callable[[FocusSession], None]
Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]


@dataclass(frozen=True, slots=True)
class CountdownConfig:
    tick_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.tick_seconds <= 0:
            raise ValueError("tick_seconds must be positive")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CountdownRunner:
    def __init__(
        self,
        *,
        clock: Clock = _utc_now,
        sleeper: Sleeper = time.sleep,
        config: CountdownConfig | None = None,
    ) -> None:
        self._clock = clock
        self._sleeper = sleeper
        self._config = config or CountdownConfig()

    def run(
        self,
        session: FocusSession,
        *,
        on_tick: TickCallback | None = None,
        on_done: DoneCallback | None = None,
    ) -> FocusSession:
        while True:
            now = self._clock()
            remaining = session.remaining_at(now)
            if on_tick is not None:
                on_tick(remaining)
            if remaining == timedelta():
                completed = session.complete()
                if on_done is not None:
                    on_done(completed)
                return completed
            self._sleeper(min(self._config.tick_seconds, remaining.total_seconds()))
