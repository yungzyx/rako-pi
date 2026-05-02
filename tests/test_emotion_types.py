"""Tests para EmotionalVector — validación de rangos."""

from __future__ import annotations

import pytest

from emotion.types import EmotionalVector


def test_valid_vector_constructs() -> None:
    v = EmotionalVector(valence=0.1, arousal=0.5, dominance=0.5)

    assert v.valence == 0.1
    assert v.arousal == 0.5
    assert v.dominance == 0.5


@pytest.mark.parametrize("valence", [-1.5, 1.5, 2.0, -2.0])
def test_valence_out_of_range_raises(valence: float) -> None:
    with pytest.raises(ValueError, match="valence"):
        EmotionalVector(valence=valence, arousal=0.5, dominance=0.5)


@pytest.mark.parametrize("arousal", [-0.1, 1.1, 2.0])
def test_arousal_out_of_range_raises(arousal: float) -> None:
    with pytest.raises(ValueError, match="arousal"):
        EmotionalVector(valence=0.0, arousal=arousal, dominance=0.5)


@pytest.mark.parametrize("dominance", [-0.1, 1.1, 2.0])
def test_dominance_out_of_range_raises(dominance: float) -> None:
    with pytest.raises(ValueError, match="dominance"):
        EmotionalVector(valence=0.0, arousal=0.5, dominance=dominance)


def test_vector_is_frozen() -> None:
    v = EmotionalVector(valence=0.0, arousal=0.5, dominance=0.5)

    with pytest.raises(Exception):
        v.valence = 0.5  # type: ignore[misc]


def test_boundary_values_accepted() -> None:
    EmotionalVector(valence=-1.0, arousal=0.0, dominance=0.0)
    EmotionalVector(valence=1.0, arousal=1.0, dominance=1.0)
