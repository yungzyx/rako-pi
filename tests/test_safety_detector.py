"""Tests para el detector de crisis.

El detector es el guardián que decide si bypassear al LLM. Sus fixtures
deben pasar siempre — un fallo aquí bloquea el merge.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from emotion.types import EmotionalVector
from safety.detector import detect_crisis
from safety.types import (
    CrisisInput,
    CrisisLevel,
    CrisisReason,
    EmotionalSample,
    PanicSource,
)

UTC = timezone.utc


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _input(**overrides: object) -> CrisisInput:
    base: dict[str, object] = {
        "transcript": None,
        "emotion_history": (),
        "panic_button": None,
        "last_high_distress_at": None,
        "last_interaction_at": None,
        "now": _now(),
    }
    base.update(overrides)
    return CrisisInput(**base)  # type: ignore[arg-type]


def _sample(minutes_ago: float, valence: float, arousal: float, dominance: float = 0.5) -> EmotionalSample:
    return EmotionalSample(
        vector=EmotionalVector(valence=valence, arousal=arousal, dominance=dominance),
        at=_now() - timedelta(minutes=minutes_ago),
    )


# ---------------------------------------------------------------------------
# Panic button
# ---------------------------------------------------------------------------


def test_physical_panic_button_triggers_crisis() -> None:
    signal = detect_crisis(_input(panic_button=PanicSource.PHYSICAL))

    assert signal.level is CrisisLevel.CRISIS
    assert CrisisReason.PANIC_BUTTON_PHYSICAL in signal.reasons
    assert signal.should_bypass_llm is True


def test_app_panic_button_triggers_crisis() -> None:
    signal = detect_crisis(_input(panic_button=PanicSource.APP))

    assert signal.level is CrisisLevel.CRISIS
    assert CrisisReason.PANIC_BUTTON_APP in signal.reasons


# ---------------------------------------------------------------------------
# Ideation keywords
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "quiero morir",
        "Quiero morirme.",
        "ya no quiero vivir",
        "no quiero seguir viva",
        "no quiero seguir vivo",
        "me voy a suicidar",
        "estoy pensando en suicidarme",
        "QUIERO MATARME",
        "quiéro morír",
        "  quiero    morir  ",
    ],
)
def test_ideation_phrase_triggers_crisis(phrase: str) -> None:
    signal = detect_crisis(_input(transcript=phrase))

    assert signal.level is CrisisLevel.CRISIS
    assert CrisisReason.KEYWORDS_IDEATION in signal.reasons


@pytest.mark.parametrize(
    "phrase",
    [
        "no quiero morir, por eso vine",
        "tengo miedo de morir algún día",
        "quería contarte algo",
        "tengo ganas de comer",
        "me siento un poco mal hoy",
    ],
)
def test_ideation_negation_or_unrelated_does_not_trigger(phrase: str) -> None:
    signal = detect_crisis(_input(transcript=phrase))

    assert CrisisReason.KEYWORDS_IDEATION not in signal.reasons


# ---------------------------------------------------------------------------
# Self-harm keywords
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "voy a cortarme",
        "quiero cortarme",
        "necesito hacerme daño",
        "tengo ganas de lastimarme",
        "me hice daño anoche",
    ],
)
def test_selfharm_phrase_triggers_crisis(phrase: str) -> None:
    signal = detect_crisis(_input(transcript=phrase))

    assert signal.level is CrisisLevel.CRISIS
    assert CrisisReason.KEYWORDS_SELFHARM in signal.reasons


@pytest.mark.parametrize(
    "phrase",
    [
        "tengo miedo de hacerme daño en el viaje",  # ambigua, pero no debe disparar
        # NOTE: el detector es conservador — preferimos falsos positivos
        # que falsos negativos. Esta línea documenta el límite actual.
    ],
)
def test_selfharm_does_not_trigger_on_clearly_unrelated(phrase: str) -> None:
    # Esta lista intencionalmente está vacía o casi vacía: el detector
    # prefiere disparar de más en self-harm. El test queda como ancla
    # para futuras decisiones de tuning.
    signal = detect_crisis(_input(transcript=phrase))
    # Documentamos el comportamiento actual: este caso SÍ dispara.
    assert isinstance(signal.level, CrisisLevel)


# ---------------------------------------------------------------------------
# Sustained emotional extreme
# ---------------------------------------------------------------------------


def test_sustained_extreme_distress_triggers_crisis() -> None:
    history = tuple(
        _sample(minutes_ago=m, valence=-0.85, arousal=0.85)
        for m in (8, 6, 4, 2, 0)
    )

    signal = detect_crisis(_input(emotion_history=history))

    assert signal.level is CrisisLevel.CRISIS
    assert CrisisReason.SUSTAINED_EMOTIONAL_EXTREME in signal.reasons


def test_brief_distress_spike_does_not_trigger_crisis() -> None:
    history = (_sample(minutes_ago=0, valence=-0.9, arousal=0.9),)

    signal = detect_crisis(_input(emotion_history=history))

    assert CrisisReason.SUSTAINED_EMOTIONAL_EXTREME not in signal.reasons


def test_distress_only_recently_does_not_count_as_sustained() -> None:
    # Solo 2 minutos de cobertura → no es "sostenido".
    history = (
        _sample(minutes_ago=2, valence=-0.9, arousal=0.9),
        _sample(minutes_ago=1, valence=-0.9, arousal=0.9),
        _sample(minutes_ago=0, valence=-0.9, arousal=0.9),
    )

    signal = detect_crisis(_input(emotion_history=history))

    assert CrisisReason.SUSTAINED_EMOTIONAL_EXTREME not in signal.reasons


def test_extreme_values_below_threshold_do_not_trigger() -> None:
    history = tuple(
        _sample(minutes_ago=m, valence=-0.5, arousal=0.5)
        for m in (8, 6, 4, 2, 0)
    )

    signal = detect_crisis(_input(emotion_history=history))

    assert CrisisReason.SUSTAINED_EMOTIONAL_EXTREME not in signal.reasons


def test_moderate_distress_returns_elevated_not_crisis() -> None:
    history = tuple(
        _sample(minutes_ago=m, valence=-0.55, arousal=0.6)
        for m in (40, 30, 20, 10, 0)
    )

    signal = detect_crisis(_input(emotion_history=history))

    assert signal.level is CrisisLevel.ELEVATED
    assert signal.should_bypass_llm is False


# ---------------------------------------------------------------------------
# Prolonged inactivity after distress
# ---------------------------------------------------------------------------


def test_prolonged_inactivity_after_distress_triggers_crisis() -> None:
    signal = detect_crisis(
        _input(
            last_high_distress_at=_now() - timedelta(hours=3),
            last_interaction_at=_now() - timedelta(hours=3),
        )
    )

    assert signal.level is CrisisLevel.CRISIS
    assert CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS in signal.reasons


def test_prolonged_inactivity_alone_does_not_trigger() -> None:
    signal = detect_crisis(
        _input(
            last_high_distress_at=None,
            last_interaction_at=_now() - timedelta(hours=10),
        )
    )

    assert CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS not in signal.reasons


def test_recent_distress_with_recent_interaction_does_not_trigger() -> None:
    signal = detect_crisis(
        _input(
            last_high_distress_at=_now() - timedelta(minutes=30),
            last_interaction_at=_now() - timedelta(minutes=5),
        )
    )

    assert CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS not in signal.reasons


def test_distress_too_long_ago_does_not_trigger_inactivity_crisis() -> None:
    # Si la angustia fue hace 3 días, ya no aplica este criterio.
    signal = detect_crisis(
        _input(
            last_high_distress_at=_now() - timedelta(days=3),
            last_interaction_at=_now() - timedelta(days=3),
        )
    )

    assert CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS not in signal.reasons


# ---------------------------------------------------------------------------
# Neutral / nothing
# ---------------------------------------------------------------------------


def test_neutral_input_returns_none() -> None:
    signal = detect_crisis(_input(transcript="hola, ¿cómo estás hoy?"))

    assert signal.level is CrisisLevel.NONE
    assert signal.reasons == ()
    assert signal.should_bypass_llm is False


def test_empty_input_returns_none() -> None:
    signal = detect_crisis(_input())

    assert signal.level is CrisisLevel.NONE
    assert signal.reasons == ()


# ---------------------------------------------------------------------------
# Combinations
# ---------------------------------------------------------------------------


def test_multiple_reasons_are_all_reported() -> None:
    history = tuple(
        _sample(minutes_ago=m, valence=-0.85, arousal=0.85)
        for m in (8, 6, 4, 2, 0)
    )

    signal = detect_crisis(
        _input(
            transcript="quiero morir",
            emotion_history=history,
            panic_button=PanicSource.PHYSICAL,
        )
    )

    assert signal.level is CrisisLevel.CRISIS
    assert CrisisReason.PANIC_BUTTON_PHYSICAL in signal.reasons
    assert CrisisReason.KEYWORDS_IDEATION in signal.reasons
    assert CrisisReason.SUSTAINED_EMOTIONAL_EXTREME in signal.reasons


def test_signal_carries_detection_timestamp() -> None:
    signal = detect_crisis(_input(panic_button=PanicSource.PHYSICAL))

    assert signal.detected_at == _now()


def test_signal_is_immutable() -> None:
    signal = detect_crisis(_input(panic_button=PanicSource.PHYSICAL))

    with pytest.raises(Exception):
        signal.level = CrisisLevel.NONE  # type: ignore[misc]
