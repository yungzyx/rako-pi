from __future__ import annotations

import hashlib
import hmac

from channels.whatsapp.webhook import (
    extract_text_messages,
    verify_meta_signature,
    verify_webhook_challenge,
)


def test_verify_webhook_challenge_requires_matching_token() -> None:
    assert (
        verify_webhook_challenge(
            mode="subscribe",
            verify_token="local-token",
            challenge="challenge-123",
            expected_verify_token="local-token",
        )
        == "challenge-123"
    )
    assert (
        verify_webhook_challenge(
            mode="subscribe",
            verify_token="wrong",
            challenge="challenge-123",
            expected_verify_token="local-token",
        )
        is None
    )


def test_extract_text_messages_from_cloud_payload() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "56912345678",
                                    "text": {"body": "estoy bien"},
                                },
                                {"from": "56900000000", "type": "image"},
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_text_messages(payload)

    assert len(messages) == 1
    assert messages[0].from_number == "56912345678"
    assert messages[0].text == "estoy bien"
    assert messages[0].message_id == "wamid.1"


def test_verify_meta_signature_uses_app_secret() -> None:
    body = b'{"hello":"world"}'
    digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()

    assert (
        verify_meta_signature(
            body=body,
            signature_header=f"sha256={digest}",
            app_secret="secret",
        )
        is True
    )
    assert (
        verify_meta_signature(
            body=body,
            signature_header="sha256=bad",
            app_secret="secret",
        )
        is False
    )
