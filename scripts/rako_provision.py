"""Provision one physical Rako for a specific user.

This CLI is designed for repeated board setup. It writes only local product
configuration to SQLite; it never stores WiFi passwords or API secrets.
"""

from __future__ import annotations

import argparse
import sys

from config import Settings
from db.database import Database
from product.user_config import UserConfigService, onboarding_status_to_dict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision local Rako user configuration")
    parser.add_argument("--name", help="Preferred user name")
    parser.add_argument("--university", help="University or institution")
    parser.add_argument("--program", help="Academic program/career")
    parser.add_argument("--timezone", default=None)
    parser.add_argument("--locale", default=None)
    parser.add_argument("--wifi-ssid", help="WiFi SSID for setup status; password is never stored")
    parser.add_argument("--whatsapp-number", help="User WhatsApp number")
    parser.add_argument("--trusted-contact-name")
    parser.add_argument("--trusted-contact-phone")
    parser.add_argument("--wellbeing-unit-name")
    parser.add_argument("--wellbeing-unit-phone")
    parser.add_argument("--enable-whatsapp", action="store_true")
    parser.add_argument("--enable-progress", action="store_true")
    parser.add_argument("--enable-proactive", action="store_true")
    parser.add_argument("--enable-wellbeing", action="store_true")
    parser.add_argument(
        "--memory",
        action="append",
        default=[],
        help="Editable normal memory, repeatable. Example: --memory 'Prefiere bloques de 25 min'",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
    try:
        status = provision(db, args)
    finally:
        db.close()

    print("Rako provisionado.")
    print(f"Ready: {status['ready']}")
    if status["missing"]:
        print("Falta configurar: " + ", ".join(status["missing"]))
    return 0 if status["ready"] else 2


def provision(db: Database, args: argparse.Namespace) -> dict[str, object]:
    service = UserConfigService(db)
    profile_patch = {
        "preferred_name": args.name,
        "university": args.university,
        "program": args.program,
        "timezone": args.timezone,
        "locale": args.locale,
    }
    if any(value is not None for value in profile_patch.values()):
        service.update_profile(profile_patch)

    channel_patch = {
        "wifi_ssid": args.wifi_ssid,
        "whatsapp_number": args.whatsapp_number,
        "trusted_contact_name": args.trusted_contact_name,
        "trusted_contact_phone": args.trusted_contact_phone,
        "wellbeing_unit_name": args.wellbeing_unit_name,
        "wellbeing_unit_phone": args.wellbeing_unit_phone,
    }
    if any(value is not None for value in channel_patch.values()):
        service.update_channels(channel_patch)

    consent_patch = {
        "whatsapp_enabled": args.enable_whatsapp or None,
        "progress_reports_enabled": args.enable_progress or None,
        "proactive_messages_enabled": args.enable_proactive or None,
        "wellbeing_escalation_enabled": args.enable_wellbeing or None,
    }
    if any(value is not None for value in consent_patch.values()):
        service.update_consent(consent_patch)

    for memory in args.memory:
        service.add_memory(text=memory, category="preference")

    return onboarding_status_to_dict(service.onboarding_status())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
