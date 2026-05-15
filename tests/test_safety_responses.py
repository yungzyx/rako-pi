"""Tests para las respuestas pre-curadas de crisis.

Verifican que cada motivo de crisis tiene una respuesta asociada y que
el selector prioriza correctamente cuando hay múltiples motivos.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from safety.responses import (
    CrisisResponse,
    pick_response,
)
from safety.types import CrisisLevel, CrisisReason, CrisisSignal

UTC = UTC


def _signal(*reasons: CrisisReason, level: CrisisLevel = CrisisLevel.CRISIS) -> CrisisSignal:
    return CrisisSignal(
        level=level,
        reasons=reasons,
        detected_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "reason",
    [
        CrisisReason.PANIC_BUTTON_PHYSICAL,
        CrisisReason.PANIC_BUTTON_APP,
        CrisisReason.KEYWORDS_IDEATION,
        CrisisReason.KEYWORDS_SELFHARM,
        CrisisReason.KEYWORDS_GOODBYE,
        CrisisReason.KEYWORDS_ABUSE_SEXUAL,
        CrisisReason.KEYWORDS_HARM_OTHERS,
        CrisisReason.KEYWORDS_DANGEROUS_ACCESS,
        CrisisReason.SUSTAINED_EMOTIONAL_EXTREME,
        CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS,
    ],
)
def test_every_crisis_reason_has_a_response(reason: CrisisReason) -> None:
    response = pick_response(_signal(reason))

    assert isinstance(response, CrisisResponse)
    assert response.id
    assert response.text.strip()
    assert response.audio_path.endswith(".wav")


def test_ideation_takes_priority_over_panic_button() -> None:
    response = pick_response(
        _signal(CrisisReason.PANIC_BUTTON_PHYSICAL, CrisisReason.KEYWORDS_IDEATION)
    )

    assert response.id == "ideation"


def test_selfharm_takes_priority_over_sustained_distress() -> None:
    response = pick_response(
        _signal(CrisisReason.SUSTAINED_EMOTIONAL_EXTREME, CrisisReason.KEYWORDS_SELFHARM)
    )

    assert response.id == "selfharm"


def test_panic_button_picked_when_alone() -> None:
    response = pick_response(_signal(CrisisReason.PANIC_BUTTON_APP))

    assert response.id == "panic"


def test_pick_response_rejects_non_crisis_signal() -> None:
    with pytest.raises(ValueError):
        pick_response(_signal(level=CrisisLevel.NONE))


def test_response_activates_trusted_contact_for_severe_reasons() -> None:
    response = pick_response(_signal(CrisisReason.KEYWORDS_IDEATION))

    assert response.activates_trusted_contact is True


def test_crisis_signal_with_only_elevated_reason_falls_back_safely() -> None:
    # Defensivo: un signal con CRISIS pero sin razones reconocidas en
    # la prioridad debe devolver una respuesta segura en vez de crashear.
    response = pick_response(_signal(CrisisReason.EMOTIONAL_DISTRESS))

    assert isinstance(response, CrisisResponse)
    assert response.id == "sustained_distress"


def test_response_text_contains_no_diagnosis_or_motivation_template() -> None:
    # No promesas vacías, no diagnósticos.
    forbidden = ("todo va a estar bien", "no es para tanto", "diagnóstico", "eres fuerte")
    response = pick_response(_signal(CrisisReason.KEYWORDS_IDEATION))

    text = response.text.lower()
    for phrase in forbidden:
        assert phrase not in text, f"forbidden phrase present: {phrase}"


def test_crisis_response_contains_udd_resources_and_confirmation() -> None:
    response = pick_response(_signal(CrisisReason.KEYWORDS_IDEATION))

    assert "+56 2 2820 3419" in response.text
    assert "800 200 125" in response.text
    assert "¿Puedes decirme que vas a contactar a alguno de estos?" in response.text
