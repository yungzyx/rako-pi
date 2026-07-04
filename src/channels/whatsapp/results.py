"""Tipos de resultado y conversores del canal WhatsApp."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from channels.whatsapp.client import WhatsAppOutboundMessage


@dataclass(frozen=True, slots=True)
class WhatsAppInboundResult:
    action: str
    response_text: str
    crisis: bool = False
    stored_mood: str | None = None
    focus_session_id: str | None = None


def inbound_result_to_dict(result: WhatsAppInboundResult) -> dict[str, object]:
    return asdict(result)


def outbound_message_to_dict(message: WhatsAppOutboundMessage) -> dict[str, object]:
    return asdict(message)


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
