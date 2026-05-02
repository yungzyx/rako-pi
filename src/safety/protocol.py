"""Orquestación del protocolo de crisis.

Sin LLM. Sin generación. Solo despacho de assets curados a:
- voz (pre-grabada)
- iluminación (estado "presente y contigo")
- notificador (contacto de confianza + recursos visibles en la app)
- journal (registro privado en SQLite)

Las dependencias se inyectan como `typing.Protocol` para que los tests
puedan usar fakes en memoria. La implementación concreta de cada uno
vive en su módulo correspondiente (`voice/`, `hardware/`, `sync/`, `db/`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from safety.responses import pick_response
from safety.types import CrisisLevel, CrisisSignal


class _VoicePlayer(Protocol):
    def play_prerecorded(self, response_id: str) -> None: ...


class _Lighting(Protocol):
    def set_present_state(self) -> None: ...


class _Notifier(Protocol):
    def notify_trusted_contact(self, signal: CrisisSignal) -> None: ...
    def show_resources(self) -> None: ...


class _Journal(Protocol):
    def record(self, signal: CrisisSignal) -> None: ...


@dataclass(frozen=True, slots=True)
class ProtocolOutcome:
    response_id: str
    notified_trusted_contact: bool
    journaled: bool


@dataclass(frozen=True, slots=True)
class CrisisProtocol:
    voice: _VoicePlayer
    lighting: _Lighting
    notifier: _Notifier
    journal: _Journal

    def execute(self, signal: CrisisSignal) -> ProtocolOutcome:
        """Despacha el protocolo completo. Solo válido para CRISIS."""
        if signal.level is not CrisisLevel.CRISIS:
            raise ValueError(
                f"execute requires CRISIS level, got {signal.level.name}"
            )

        # Registro privado primero — si algo falla más adelante, el
        # evento queda anotado para que el contacto pueda revisar.
        self.journal.record(signal)

        response = pick_response(signal)

        # Voz + iluminación: presencia inmediata.
        self.voice.play_prerecorded(response.id)
        self.lighting.set_present_state()

        notified = False
        if response.activates_trusted_contact:
            self.notifier.notify_trusted_contact(signal)
            notified = True
        self.notifier.show_resources()

        return ProtocolOutcome(
            response_id=response.id,
            notified_trusted_contact=notified,
            journaled=True,
        )
