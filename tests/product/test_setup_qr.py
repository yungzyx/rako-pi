from __future__ import annotations

from config import Settings
from product.setup_qr import build_setup_qr_payload, render_setup_card_svg


def test_setup_qr_payload_has_no_secret() -> None:
    settings = Settings(
        _env_file=None,
        rako_device_id="rako-001",
        rako_api_token="super-secret",
    )

    payload = build_setup_qr_payload(settings, serial="SN-001", lot="pilot-a")

    assert payload.includes_secret is False
    assert "super-secret" not in payload.qr_text
    assert "serial=SN-001" in payload.qr_text
    assert payload.ssid.startswith("Rako-Setup")


def test_setup_card_svg_is_printable() -> None:
    settings = Settings(_env_file=None, rako_device_id="rako-001")
    payload = build_setup_qr_payload(settings, serial="SN-001", lot="pilot-a")

    svg = render_setup_card_svg(payload)

    assert svg.startswith("<svg")
    assert "Rako Setup" in svg
    assert "No incluye token" in svg
