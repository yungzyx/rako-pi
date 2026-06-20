from __future__ import annotations

import pytest

from productivity.mindfulness import (
    get_mindfulness_exercise,
    list_mindfulness_exercises,
    pick_mindfulness_exercise,
)


def test_mindfulness_library_has_short_safe_exercises() -> None:
    exercises = list_mindfulness_exercises()

    assert len(exercises) >= 5
    assert all(1 <= exercise.minutes <= 5 for exercise in exercises)
    assert all(exercise.script for exercise in exercises)
    assert any(exercise.id == "body_scan_short" for exercise in exercises)


def test_pick_mindfulness_exercise_uses_context_and_duration() -> None:
    exercise = pick_mindfulness_exercise(context="low_mood", max_minutes=3)

    assert exercise.id == "body_scan_short"
    assert "tensión" in exercise.prompt


def test_get_mindfulness_exercise_rejects_unknown_id() -> None:
    with pytest.raises(KeyError):
        get_mindfulness_exercise("missing")  # type: ignore[arg-type]
