"""Integración: protocolo de crisis + CrisisJournal real (SQLite).

Este test cierra el loop entre `safety/` y `db/` — verifica que un
disparo de crisis termina con un row persistido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from db.connection import open_connection
from db.journal import CrisisJournal
from db.schema import create_all
from safety.protocol import CrisisProtocol
from safety.types import CrisisLevel, CrisisReason, CrisisSignal

UTC = timezone.utc


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


def test_crisis_protocol_writes_to_real_journal() -> None:
    conn = open_connection(":memory:")
    create_all(conn)
    journal = CrisisJournal(conn)
    protocol = CrisisProtocol(
        voice=_FakeVoice(),
        lighting=_FakeLighting(),
        notifier=_FakeNotifier(),
        journal=journal,
    )
    signal = CrisisSignal(
        level=CrisisLevel.CRISIS,
        reasons=(CrisisReason.KEYWORDS_IDEATION,),
        detected_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
    )

    protocol.execute(signal)

    entries = journal.list_recent()
    assert len(entries) == 1
    assert entries[0].reasons == ("KEYWORDS_IDEATION",)
    assert entries[0].level == "CRISIS"
