"""Tests del análisis de patrones (señal de bloqueo / proactividad)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from emotion.patterns import (
    BlockLevel,
    BlockReason,
    BlockSignal,
    PatternInput,
    analyze_patterns,
)

UTC = UTC


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _input(**overrides: object) -> PatternInput:
    base: dict[str, object] = {
        "last_interaction_at": _now() - timedelta(minutes=10),
        "pending_task_count": 0,
        "do_not_disturb": False,
        "now": _now(),
    }
    base.update(overrides)
    return PatternInput(**base)  # type: ignore[arg-type]


def test_no_signal_for_recent_interaction_and_no_load() -> None:
    signal = analyze_patterns(_input())

    assert signal.level is BlockLevel.NONE
    assert signal.reasons == ()


def test_moderate_inactivity_triggers_mild() -> None:
    signal = analyze_patterns(_input(last_interaction_at=_now() - timedelta(hours=5)))

    assert signal.level is BlockLevel.MILD
    assert BlockReason.PROLONGED_INACTIVITY in signal.reasons


def test_long_inactivity_triggers_moderate() -> None:
    signal = analyze_patterns(_input(last_interaction_at=_now() - timedelta(hours=14)))

    assert signal.level is BlockLevel.MODERATE
    assert BlockReason.PROLONGED_INACTIVITY in signal.reasons


def test_high_pending_load_triggers_mild() -> None:
    signal = analyze_patterns(_input(pending_task_count=12))

    assert signal.level is BlockLevel.MILD
    assert BlockReason.HIGH_PENDING_LOAD in signal.reasons


def test_combined_factors_escalate_level() -> None:
    signal = analyze_patterns(
        _input(
            last_interaction_at=_now() - timedelta(hours=14),
            pending_task_count=12,
        )
    )

    assert signal.level is BlockLevel.MODERATE
    assert BlockReason.PROLONGED_INACTIVITY in signal.reasons
    assert BlockReason.HIGH_PENDING_LOAD in signal.reasons


def test_do_not_disturb_suppresses_everything() -> None:
    signal = analyze_patterns(
        _input(
            last_interaction_at=_now() - timedelta(days=2),
            pending_task_count=50,
            do_not_disturb=True,
        )
    )

    assert signal.level is BlockLevel.NONE
    assert signal.reasons == ()


def test_no_prior_interaction_returns_none() -> None:
    # Si nunca hubo interacción, no podemos detectar "inactividad".
    signal = analyze_patterns(_input(last_interaction_at=None))

    assert signal.level is BlockLevel.NONE


def test_late_night_with_inactivity_flags_late_night() -> None:
    # Despertar a las 3am tras silencio sostenido es señal a vigilar.
    late_now = datetime(2026, 5, 1, 3, 30, tzinfo=UTC)
    signal = analyze_patterns(
        PatternInput(
            last_interaction_at=late_now - timedelta(hours=8),
            pending_task_count=0,
            do_not_disturb=False,
            now=late_now,
        )
    )

    assert BlockReason.LATE_NIGHT in signal.reasons


def test_signal_is_immutable() -> None:
    signal = analyze_patterns(_input())

    import pytest

    with pytest.raises(Exception):
        signal.level = BlockLevel.MODERATE  # type: ignore[misc]


def test_signal_carries_detection_timestamp() -> None:
    signal = analyze_patterns(_input())

    assert isinstance(signal, BlockSignal)
    assert signal.detected_at == _now()
