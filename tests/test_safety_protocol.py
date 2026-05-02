"""Tests para la orquestación del protocolo de crisis.

Usa fakes en memoria que cumplen los Protocols definidos en
`safety.protocol`. Verifica el orden y la totalidad de los efectos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from safety.protocol import CrisisProtocol, ProtocolOutcome
from safety.types import CrisisLevel, CrisisReason, CrisisSignal

UTC = UTC


@dataclass
class _FakeVoice:
    played: list[str] = field(default_factory=list)

    def play_prerecorded(self, response_id: str) -> None:
        self.played.append(response_id)


@dataclass
class _FakeLighting:
    present_set: int = 0

    def set_present_state(self) -> None:
        self.present_set += 1


@dataclass
class _FakeNotifier:
    contacts_notified: list[CrisisSignal] = field(default_factory=list)
    resources_shown: int = 0

    def notify_trusted_contact(self, signal: CrisisSignal) -> None:
        self.contacts_notified.append(signal)

    def show_resources(self) -> None:
        self.resources_shown += 1


@dataclass
class _FakeJournal:
    entries: list[CrisisSignal] = field(default_factory=list)

    def record(self, signal: CrisisSignal) -> None:
        self.entries.append(signal)


def _signal(*reasons: CrisisReason, level: CrisisLevel = CrisisLevel.CRISIS) -> CrisisSignal:
    return CrisisSignal(
        level=level,
        reasons=reasons,
        detected_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
    )


def _build_protocol() -> tuple[
    CrisisProtocol, _FakeVoice, _FakeLighting, _FakeNotifier, _FakeJournal
]:
    voice, lighting, notifier, journal = (
        _FakeVoice(),
        _FakeLighting(),
        _FakeNotifier(),
        _FakeJournal(),
    )
    protocol = CrisisProtocol(
        voice=voice,
        lighting=lighting,
        notifier=notifier,
        journal=journal,
    )
    return protocol, voice, lighting, notifier, journal


def test_executes_full_sequence_for_crisis() -> None:
    protocol, voice, lighting, notifier, journal = _build_protocol()
    signal = _signal(CrisisReason.KEYWORDS_IDEATION)

    outcome = protocol.execute(signal)

    assert isinstance(outcome, ProtocolOutcome)
    assert outcome.response_id == "ideation"
    assert voice.played == ["ideation"]
    assert lighting.present_set == 1
    assert notifier.contacts_notified == [signal]
    assert notifier.resources_shown == 1
    assert journal.entries == [signal]


def test_does_not_notify_contact_if_response_says_so() -> None:
    # PROLONGED_INACTIVITY_AFTER_DISTRESS no escala automáticamente al
    # contacto de confianza (solo "presencia" + recursos).
    protocol, _voice, _lighting, notifier, journal = _build_protocol()
    signal = _signal(CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS)

    outcome = protocol.execute(signal)

    assert outcome.notified_trusted_contact is False
    assert notifier.contacts_notified == []
    # Pero recursos y journal sí siempre.
    assert notifier.resources_shown == 1
    assert journal.entries == [signal]


def test_journals_even_if_voice_fails() -> None:
    # Si la voz falla, el evento debe quedar registrado igual.
    @dataclass
    class _FailingVoice:
        def play_prerecorded(self, response_id: str) -> None:
            raise RuntimeError("speaker offline")

    voice = _FailingVoice()
    lighting, notifier, journal = _FakeLighting(), _FakeNotifier(), _FakeJournal()
    protocol = CrisisProtocol(voice=voice, lighting=lighting, notifier=notifier, journal=journal)
    signal = _signal(CrisisReason.PANIC_BUTTON_PHYSICAL)

    with pytest.raises(RuntimeError):
        protocol.execute(signal)

    # Aún así el evento queda registrado (privacidad: el usuario debe
    # poder revisar lo que pasó).
    assert journal.entries == [signal]


def test_rejects_non_crisis_signal() -> None:
    protocol, *_ = _build_protocol()
    signal = _signal(level=CrisisLevel.NONE)

    with pytest.raises(ValueError):
        protocol.execute(signal)


def test_rejects_elevated_signal() -> None:
    protocol, *_ = _build_protocol()
    signal = _signal(level=CrisisLevel.ELEVATED)

    with pytest.raises(ValueError):
        protocol.execute(signal)
