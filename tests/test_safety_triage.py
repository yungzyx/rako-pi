"""Tests del triage graduado no-crisis (src/safety/triage.py).

El triage decide, DESPUÉS de que el detector de crisis dijo que no hay
crisis, cómo diferenciar los casos: consejo clínico (fuera de rol),
revelación personal (derivar a bienestar), estrés académico (LLM con
nota de tono), patrón recurrente (derivar), o conversación normal.

Estos tests son parte del gate de seguridad de CI — la diferenciación
de casos no puede regresionar en silencio.
"""

from __future__ import annotations

import pytest

from safety.triage import RECURRENCE_LOW_MOOD_DAYS, TriageLevel, triage_turn

# ---------------------------------------------------------------------------
# Consejo clínico → fuera de rol (redirección dura, como siempre)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "¿qué medicamento debería tomar para la ansiedad?",
        "¿me recomiendas alguna pastilla para dormir?",
        "¿puedo dejar de tomar mi antidepresivo?",
        "¿qué dosis de ansiolítico es normal?",
        "¿será que tengo un trastorno?",
    ],
)
def test_clinical_advice_requests_stay_out_of_scope(phrase: str) -> None:
    result = triage_turn(phrase)

    assert result.level is TriageLevel.CLINICAL_SCOPE


# ---------------------------------------------------------------------------
# Revelación personal → derivación a la unidad de bienestar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "me diagnosticaron depresión el año pasado",
        "necesito terapia por trauma",
        "necesito un psicólogo",
        "quiero ir al psicólogo pero no sé cómo",
        "sufro de ansiedad desde el colegio",
        "estoy en tratamiento por depresión",
    ],
)
def test_strong_personal_disclosure_refers_to_wellbeing(phrase: str) -> None:
    result = triage_turn(phrase)

    assert result.level is TriageLevel.WELLBEING_REFERRAL


@pytest.mark.parametrize(
    "phrase",
    [
        "creo que tengo ansiedad",
        "tengo depresión y no le he contado a nadie",
        "estoy deprimido",
    ],
)
def test_personal_disclosure_without_academic_frame_refers_to_wellbeing(phrase: str) -> None:
    result = triage_turn(phrase)

    assert result.level is TriageLevel.WELLBEING_REFERRAL


def test_strong_disclosure_refers_even_with_academic_frame() -> None:
    # "Me diagnosticaron" es revelación fuerte: la prueba de mañana no
    # convierte esto en estrés académico pasajero.
    result = triage_turn("me diagnosticaron depresión y tengo prueba mañana")

    assert result.level is TriageLevel.WELLBEING_REFERRAL


# ---------------------------------------------------------------------------
# Mención en marco académico → LLM con nota de tono (NO redirección fría)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "tengo ansiedad por la prueba de mañana",
        "me da ansiedad el examen de cálculo",
        "estoy con ansiedad por el certamen del ramo",
    ],
)
def test_academic_stress_mention_goes_to_llm_with_support(phrase: str) -> None:
    result = triage_turn(phrase)

    assert result.level is TriageLevel.SUPPORTIVE_ACADEMIC


@pytest.mark.parametrize(
    "phrase",
    [
        "me siento muy solo últimamente",
        "no me dan ganas de nada esta semana",
        "lo estoy pasando muy mal",
    ],
)
def test_emotional_distress_without_clinical_vocab_gets_supportive_llm(phrase: str) -> None:
    result = triage_turn(phrase)

    assert result.level is TriageLevel.SUPPORTIVE_ACADEMIC


# ---------------------------------------------------------------------------
# Recurrencia: ánimo bajo sostenido en la semana sube el nivel
# ---------------------------------------------------------------------------


def test_recurring_low_mood_upgrades_academic_stress_to_referral() -> None:
    result = triage_turn(
        "tengo ansiedad por la prueba de mañana",
        recent_low_mood_days=RECURRENCE_LOW_MOOD_DAYS,
    )

    assert result.level is TriageLevel.WELLBEING_REFERRAL


def test_recurring_low_mood_upgrades_distress_to_referral() -> None:
    result = triage_turn(
        "no me dan ganas de nada esta semana",
        recent_low_mood_days=RECURRENCE_LOW_MOOD_DAYS + 1,
    )

    assert result.level is TriageLevel.WELLBEING_REFERRAL


def test_recurring_low_mood_alone_does_not_touch_neutral_turns() -> None:
    # Sin mención emocional ni estado elevado, un historial de ánimo bajo
    # no convierte "quiero estudiar" en una derivación.
    result = triage_turn("quiero estudiar cálculo 25 minutos", recent_low_mood_days=5)

    assert result.level is TriageLevel.ACADEMIC


# ---------------------------------------------------------------------------
# Estado emocional elevado (del detector) sin mención en texto
# ---------------------------------------------------------------------------


def test_elevated_without_topic_gets_elevated_support() -> None:
    result = triage_turn("no sé por dónde partir hoy", elevated=True)

    assert result.level is TriageLevel.ELEVATED_SUPPORT


def test_elevated_with_recurring_low_mood_refers_to_wellbeing() -> None:
    result = triage_turn(
        "no sé por dónde partir hoy",
        elevated=True,
        recent_low_mood_days=RECURRENCE_LOW_MOOD_DAYS,
    )

    assert result.level is TriageLevel.WELLBEING_REFERRAL


# ---------------------------------------------------------------------------
# Mención suelta de tema clínico (ni personal ni académica) → fuera de rol
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "¿qué es la depresión?",
        "háblame del trastorno bipolar",
    ],
)
def test_bare_clinical_topic_stays_out_of_scope(phrase: str) -> None:
    result = triage_turn(phrase)

    assert result.level is TriageLevel.CLINICAL_SCOPE


# ---------------------------------------------------------------------------
# Conversación normal → ACADEMIC (LLM sin nota)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "quiero estudiar cálculo 25 minutos",
        "hazme un pomodoro",
        "¿qué hago primero, el informe o la guía?",
        "hola rako, ¿cómo estás?",
    ],
)
def test_neutral_turns_are_academic(phrase: str) -> None:
    result = triage_turn(phrase)

    assert result.level is TriageLevel.ACADEMIC


# ---------------------------------------------------------------------------
# Metadatos del resultado
# ---------------------------------------------------------------------------


def test_result_carries_a_reason_string() -> None:
    result = triage_turn("necesito terapia por trauma")

    assert isinstance(result.reason, str)
    assert result.reason


def test_result_is_immutable() -> None:
    result = triage_turn("hola")

    with pytest.raises(Exception):
        result.level = TriageLevel.ACADEMIC  # type: ignore[misc]
