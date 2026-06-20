"""WhatsApp Cloud webhook helpers."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WhatsAppWebhookMessage:
    from_number: str
    text: str
    message_id: str | None = None


def verify_webhook_challenge(
    *,
    mode: str | None,
    verify_token: str | None,
    challenge: str | None,
    expected_verify_token: str | None,
) -> str | None:
    if (
        mode == "subscribe"
        and challenge
        and expected_verify_token
        and verify_token == expected_verify_token
    ):
        return challenge
    return None


def extract_text_messages(payload: dict[str, Any]) -> tuple[WhatsAppWebhookMessage, ...]:
    messages: list[WhatsAppWebhookMessage] = []
    for entry in _as_list(payload.get("entry")):
        for change in _as_list(_as_dict(entry).get("changes")):
            value = _as_dict(_as_dict(change).get("value"))
            for message in _as_list(value.get("messages")):
                message_dict = _as_dict(message)
                text = _as_dict(message_dict.get("text")).get("body")
                from_number = message_dict.get("from")
                if isinstance(from_number, str) and isinstance(text, str) and text.strip():
                    messages.append(
                        WhatsAppWebhookMessage(
                            from_number=from_number,
                            text=text,
                            message_id=str(message_dict.get("id") or "") or None,
                        )
                    )
    return tuple(messages)


def verify_meta_signature(
    *,
    body: bytes,
    signature_header: str | None,
    app_secret: str | None,
) -> bool:
    if not app_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
