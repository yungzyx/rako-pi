from __future__ import annotations

import httpx
import pytest

from channels.whatsapp.client import WhatsAppCloudClient


def test_whatsapp_cloud_client_sends_text_payload_without_leaking_token() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["json"] = request.read().decode()
        return httpx.Response(200, json={"messages": [{"id": "wamid.test"}]})

    client = WhatsAppCloudClient(
        access_token="token-secret",
        phone_number_id="12345",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    message = client.send_text(to="+56912345678", text="hola", kind="CHECKIN")

    assert seen["url"] == "https://graph.facebook.com/v20.0/12345/messages"
    assert seen["auth"] == "Bearer token-secret"
    assert '"body":"hola"' in seen["json"]
    assert message.metadata["provider"] == "whatsapp_cloud"
    assert message.metadata["provider_message_id"] == "wamid.test"
    assert "token-secret" not in str(message)


def test_whatsapp_cloud_client_raises_on_api_error() -> None:
    client = WhatsAppCloudClient(
        access_token="token-secret",
        phone_number_id="12345",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(401, json={}))
        ),
    )

    with pytest.raises(RuntimeError, match="WhatsApp Cloud API failed"):
        client.send_text(to="+56912345678", text="hola", kind="CHECKIN")
