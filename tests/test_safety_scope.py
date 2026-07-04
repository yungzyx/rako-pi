"""Tests para las guardrails de alcance académico (src/safety/scope.py).

`mentions_mental_health_topic` es parte del mismo gate que evita que temas
clínicos lleguen al LLM (ver `Orchestrator.handle_turn`) — no tenía tests
dedicados pese a eso.
"""

from __future__ import annotations

import pytest

from safety.scope import (
    build_elevated_support_response,
    build_scope_redirect_response,
    mentions_mental_health_topic,
)


@pytest.mark.parametrize(
    "phrase",
    [
        "tengo mucha ansiedad antes de las pruebas",
        "creo que tengo depresión",
        "mi psicóloga me dijo que hiciera esto",
        "¿debería tomar un ansiolítico?",
        "tengo un trastorno de ansiedad diagnosticado",
        "ANSIEDAD",
        "Ansiedad",
        "ansíedad",
        "estoy en terapia hace un año",
        "vivo con estrés postraumático",
    ],
)
def test_mentions_mental_health_topic_detects_clinical_vocab(phrase: str) -> None:
    assert mentions_mental_health_topic(phrase) is True


@pytest.mark.parametrize(
    "phrase",
    [
        "tengo que estudiar cálculo para la prueba",
        "quiero organizar mi semana",
        "hazme un pomodoro de 25 minutos",
        "restregar el piso me tomó una hora",  # guarda contra falso positivo de "estres"
        "",
    ],
)
def test_mentions_mental_health_topic_ignores_neutral_academic_phrases(phrase: str) -> None:
    assert mentions_mental_health_topic(phrase) is False


def test_scope_redirect_response_mentions_academic_role_and_udd_resources() -> None:
    text = build_scope_redirect_response()

    assert "Bienestar UDD" in text
    assert "diagnóstico" not in text.lower()
    assert "supera mi rol" in text


def test_elevated_support_response_offers_concrete_step_and_udd_resources() -> None:
    text = build_elevated_support_response()

    assert "Bienestar UDD" in text
    assert "primer paso" in text
