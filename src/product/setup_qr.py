"""Setup QR payloads and printable SVG cards."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html import escape
from typing import Any

from config import Settings
from product.hotspot_setup import build_hotspot_plan


@dataclass(frozen=True, slots=True)
class SetupQrPayload:
    device_id: str | None
    ssid: str
    setup_url: str
    serial: str | None
    lot: str | None
    qr_text: str
    includes_secret: bool


def build_setup_qr_payload(
    settings: Settings,
    *,
    serial: str | None = None,
    lot: str | None = None,
) -> SetupQrPayload:
    hotspot = build_hotspot_plan(settings)
    qr_text = "\n".join(
        (
            "RAKO_SETUP",
            f"device_id={settings.rako_device_id or ''}",
            f"serial={serial or ''}",
            f"lot={lot or ''}",
            f"ssid={hotspot.ssid}",
            f"url={hotspot.setup_url}",
        )
    )
    return SetupQrPayload(
        device_id=settings.rako_device_id,
        ssid=hotspot.ssid,
        setup_url=hotspot.setup_url,
        serial=serial,
        lot=lot,
        qr_text=qr_text,
        includes_secret=False,
    )


def setup_qr_payload_to_dict(payload: SetupQrPayload) -> dict[str, Any]:
    return asdict(payload)


def render_setup_card_svg(payload: SetupQrPayload) -> str:
    """Render a printable card with QR payload text and setup instructions.

    This is intentionally dependency-free. The `qr_text` is stable and can be
    fed into a QR generator in packaging/factory tooling.
    """

    lines = [
        "1. Enciende Rako.",
        f"2. Conéctate a WiFi {payload.ssid}.",
        f"3. Abre {payload.setup_url}.",
        "4. Completa perfil, consentimiento y prueba de hardware.",
    ]
    payload_lines = payload.qr_text.splitlines()
    instructions = "".join(
        f'<text x="36" y="{178 + index * 20}" class="small">{escape(line)}</text>'
        for index, line in enumerate(lines)
    )
    qr_lines = "".join(
        f'<text x="300" y="{78 + index * 18}" class="mono">{escape(line)}</text>'
        for index, line in enumerate(payload_lines)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="360" viewBox="0 0 720 360">
  <style>
    .title {{ font: 700 28px system-ui, sans-serif; fill: #17202a; }}
    .label {{ font: 700 14px system-ui, sans-serif; fill: #3758a8; }}
    .small {{ font: 15px system-ui, sans-serif; fill: #303946; }}
    .mono {{ font: 13px ui-monospace, monospace; fill: #17202a; }}
    .box {{ fill: #fff; stroke: #d8dde6; stroke-width: 2; rx: 12; }}
    .qr {{ fill: #f5f7fb; stroke: #17202a; stroke-width: 2; rx: 8; }}
  </style>
  <rect x="12" y="12" width="696" height="336" class="box"/>
  <text x="36" y="58" class="title">Rako Setup</text>
  <text x="36" y="88" class="small">Dispositivo: {escape(payload.device_id or "sin-id")}</text>
  <text x="36" y="114" class="small">Serial: {escape(payload.serial or "sin-serial")}</text>
  <text x="36" y="140" class="label">Instrucciones</text>
  {instructions}
  <rect x="286" y="40" width="390" height="250" class="qr"/>
  <text x="300" y="58" class="label">Payload para QR</text>
  {qr_lines}
  <text x="300" y="318" class="small">No incluye token ni contraseña WiFi.</text>
</svg>"""
