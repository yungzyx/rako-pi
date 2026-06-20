"""WhatsApp client boundary.

The first implementation is intentionally in-memory. The production adapter can
later implement the same small interface using WhatsApp Cloud API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx


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


class WhatsAppCloudClient:
    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        api_version: str = "v20.0",
        timeout_s: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("WhatsApp Cloud access token is required")
        if not phone_number_id:
            raise ValueError("WhatsApp Cloud phone number id is required")
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._api_version = api_version.strip("/") or "v20.0"
        self._client = http_client or httpx.Client(timeout=timeout_s)

    def send_text(
        self,
        *,
        to: str,
        text: str,
        kind: str,
        metadata: dict[str, str] | None = None,
    ) -> WhatsAppOutboundMessage:
        response = self._client.post(
            f"https://graph.facebook.com/{self._api_version}/{self._phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self._access_token}"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"WhatsApp Cloud API failed: {response.status_code}") from exc
        payload = response.json()
        messages = payload.get("messages") if isinstance(payload, dict) else None
        message_id = None
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            message_id = str(messages[0].get("id") or "") or None
        outbound_metadata = dict(metadata or {})
        outbound_metadata["provider"] = "whatsapp_cloud"
        if message_id:
            outbound_metadata["provider_message_id"] = message_id
        return WhatsAppOutboundMessage(
            to=to,
            text=text,
            kind=kind,
            metadata=outbound_metadata,
        )
