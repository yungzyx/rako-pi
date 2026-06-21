"""Factory helper for preparing many Rako boards.

Default mode is dry-run: print per-device env values, setup QR payload, and
post-flash checks. Use `--write-env PATH` only on the target board.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

from config import Settings
from product.setup_qr import build_setup_qr_payload, render_setup_card_svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare factory values for a Rako board")
    parser.add_argument("--serial", required=True, help="Physical serial number")
    parser.add_argument("--lot", required=True, help="Manufacturing lot")
    parser.add_argument("--device-id", help="Override device id; default is rako-<serial>")
    parser.add_argument("--write-env", help="Write generated values to this env file")
    parser.add_argument("--write-card-svg", help="Write printable setup card SVG")
    args = parser.parse_args(argv)

    device_id = _clean_id(args.device_id or f"rako-{args.serial}")
    api_token = secrets.token_urlsafe(32)
    sqlite_key = secrets.token_hex(32)
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_device_id=device_id,
        rako_api_token=api_token,
        sqlite_encryption_key=sqlite_key,
        rako_setup_hotspot_enabled=True,
    )
    payload = build_setup_qr_payload(settings, serial=args.serial, lot=args.lot)
    env_text = "\n".join(
        (
            "RAKO_ENV=prod",
            f"RAKO_DEVICE_ID={device_id}",
            f"RAKO_API_TOKEN={api_token}",
            f"SQLITE_ENCRYPTION_KEY={sqlite_key}",
            "RAKO_SETUP_HOTSPOT_ENABLED=true",
            "RAKO_WIFI_APPLY_ENABLED=true",
            "",
        )
    )

    print("Rako factory image values")
    print(f"device_id: {device_id}")
    print(f"serial: {args.serial}")
    print(f"lot: {args.lot}")
    print(f"setup_ssid: {payload.ssid}")
    print(f"setup_url: {payload.setup_url}")
    print("\nPost-flash checks:")
    print("  rako-doctor --factory --full")
    print("  rako-api and open /setup from phone")
    print("  POST /hardware/checks for microphone/speaker/oled/button/focus_flow/crisis_bypass")
    print("\nEnv values:")
    print(env_text)

    if args.write_env:
        Path(args.write_env).write_text(env_text, encoding="utf-8")
        print(f"Wrote env values to {args.write_env}")
    if args.write_card_svg:
        Path(args.write_card_svg).write_text(render_setup_card_svg(payload), encoding="utf-8")
        print(f"Wrote setup card SVG to {args.write_card_svg}")
    return 0


def _clean_id(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return clean[:80] or f"rako-{secrets.token_hex(6)}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
