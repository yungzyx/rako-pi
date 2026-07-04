"""Shared crisis-recency check for outbound coaching/scheduling.

Neither `productivity/` nor `channels/whatsapp/scheduler.py` run crisis
detection themselves — they only need to know "did a crisis fire recently?"
so a scheduled nudge doesn't compete with the safety protocol. This keeps
that check in one place instead of duplicating `crisis_journal` queries.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database

_DEFAULT_LOOKBACK = timedelta(hours=24)


def has_recent_crisis_event(
    db: Database,
    *,
    now: datetime,
    lookback: timedelta = _DEFAULT_LOOKBACK,
) -> bool:
    """True si hubo una crisis registrada dentro de `lookback` antes de `now`."""
    cutoff = _ensure_aware(now) - lookback
    return any(
        _ensure_aware(entry.detected_at) >= cutoff for entry in db.crisis_journal.list_recent()
    )


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
