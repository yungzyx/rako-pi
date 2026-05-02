"""Tests del detector de wake-word (substring matcher para dev/CI)."""

from __future__ import annotations

import pytest

from voice.wake_word import (
    SubstringWakeWordDetector,
    WakeWordDetector,
    WakeWordHit,
)


def test_satisfies_protocol() -> None:
    detector: WakeWordDetector = SubstringWakeWordDetector(("hey rako",))
    assert hasattr(detector, "detect")


def test_detects_exact_phrase() -> None:
    detector = SubstringWakeWordDetector(("hey rako",))

    hit = detector.detect("hey rako, ¿podemos hablar?")

    assert isinstance(hit, WakeWordHit)
    assert hit.phrase == "hey rako"


def test_detection_is_case_insensitive() -> None:
    detector = SubstringWakeWordDetector(("hey rako",))

    assert detector.detect("HEY RAKO") is not None
    assert detector.detect("Hey Rako") is not None


def test_detection_is_accent_insensitive() -> None:
    detector = SubstringWakeWordDetector(("oye rako",))

    assert detector.detect("Óye Rakó") is not None


def test_returns_first_matching_phrase_when_multiple_configured() -> None:
    detector = SubstringWakeWordDetector(("hey rako", "hola rako", "oye rako"))

    hit = detector.detect("hola rako, te necesito")

    assert hit is not None
    assert hit.phrase == "hola rako"


def test_no_match_returns_none() -> None:
    detector = SubstringWakeWordDetector(("hey rako",))

    assert detector.detect("buenos días") is None


def test_empty_text_returns_none() -> None:
    detector = SubstringWakeWordDetector(("hey rako",))

    assert detector.detect("") is None
    assert detector.detect("   ") is None


def test_rejects_empty_phrase_list_at_construction() -> None:
    with pytest.raises(ValueError):
        SubstringWakeWordDetector(())


def test_rejects_empty_phrase_in_list() -> None:
    with pytest.raises(ValueError):
        SubstringWakeWordDetector(("hey rako", ""))


def test_match_must_be_at_word_boundary() -> None:
    # "rakón" no debe disparar "rako".
    detector = SubstringWakeWordDetector(("rako",))

    assert detector.detect("rakón llegó") is None
    assert detector.detect("rako llegó") is not None
