"""Tests del InteractionRepository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.repositories import InteractionRepository
from db.types import Interaction, InteractionType
from emotion.types import EmotionalVector

UTC = UTC


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _new_interaction(
    *,
    id: str = "i1",
    timestamp: datetime | None = None,
    type: InteractionType = InteractionType.USER_VOICE,
    transcription_excerpt: str | None = None,
    emotion: EmotionalVector | None = None,
    response_id: str | None = None,
    response_text: str | None = None,
) -> Interaction:
    return Interaction(
        id=id,
        timestamp=timestamp or _now(),
        type=type,
        transcription_excerpt=transcription_excerpt,
        emotion=emotion,
        response_id=response_id,
        response_text=response_text,
    )


def test_append_and_retrieve(db_conn) -> None:
    repo = InteractionRepository(db_conn)
    interaction = _new_interaction(
        transcription_excerpt="hola",
        emotion=EmotionalVector(0.1, 0.2, 0.5),
    )

    saved = repo.append(interaction)

    assert saved == interaction
    assert repo.list_recent()[0] == interaction


def test_append_truncates_long_transcription(db_conn) -> None:
    # Privacidad: la transcripción nunca debería persistirse completa.
    long_text = "x" * 1000
    repo = InteractionRepository(db_conn)
    repo.append(_new_interaction(transcription_excerpt=long_text))

    saved = repo.list_recent()[0]
    assert saved.transcription_excerpt is not None
    assert len(saved.transcription_excerpt) <= 200


def test_list_recent_orders_newest_first(db_conn) -> None:
    repo = InteractionRepository(db_conn)
    repo.append(_new_interaction(id="old", timestamp=_now() - timedelta(hours=1)))
    repo.append(_new_interaction(id="new", timestamp=_now()))

    recent = repo.list_recent()

    assert recent[0].id == "new"
    assert recent[1].id == "old"


def test_list_recent_respects_limit(db_conn) -> None:
    repo = InteractionRepository(db_conn)
    for i in range(5):
        repo.append(_new_interaction(id=f"i{i}", timestamp=_now() - timedelta(minutes=i)))

    assert len(repo.list_recent(limit=3)) == 3


def test_list_recent_rejects_non_positive_limit(db_conn) -> None:
    repo = InteractionRepository(db_conn)

    import pytest

    for bad in (0, -1):
        with pytest.raises(ValueError):
            repo.list_recent(limit=bad)


def test_emotion_round_trip(db_conn) -> None:
    repo = InteractionRepository(db_conn)
    vector = EmotionalVector(-0.5, 0.7, 0.3)
    repo.append(_new_interaction(emotion=vector))

    saved = repo.list_recent()[0]

    assert saved.emotion == vector


def test_emotion_can_be_null(db_conn) -> None:
    repo = InteractionRepository(db_conn)
    repo.append(_new_interaction(emotion=None))

    saved = repo.list_recent()[0]

    assert saved.emotion is None


def test_purge_all(db_conn) -> None:
    repo = InteractionRepository(db_conn)
    repo.append(_new_interaction(id="a"))
    repo.append(_new_interaction(id="b"))

    deleted = repo.purge_all()

    assert deleted == 2
    assert repo.list_recent() == []
