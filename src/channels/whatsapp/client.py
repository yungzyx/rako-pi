"""WhatsApp client boundary.

The first implementation is intentionally in-memory. The production adapter can
later implement the same small interface using WhatsApp Cloud API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WhatsAppOutboundMessage:
    to: str
    text: str
    kind: str
    metadata: dict[str, str] = field(default_factory=dict)


class WhatsAppClient(Protocol):
    def send_text(
        self,
        *,
        to: str,
        text: str,
        kind: str,
        metadata: dict[str, str] | None = None,
    ) -> WhatsAppOutboundMessage: ...


class InMemoryWhatsAppClient:
    def __init__(self) -> None:
        self.sent: list[WhatsAppOutboundMessage] = []

    def send_text(
        self,
        *,
        to: str,
        text: str,
        kind: str,
        metadata: dict[str, str] | None = None,
    ) -> WhatsAppOutboundMessage:
        message = WhatsAppOutboundMessage(
            to=to,
            text=text,
            kind=kind,
            metadata=metadata or {},
        )
        self.sent.append(message)
        return message
