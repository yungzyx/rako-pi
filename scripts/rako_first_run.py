#!/usr/bin/env python3
"""One-shot first-run setup for a delivered Rako unit."""

from __future__ import annotations

import argparse
import json
import sys

from config import Settings
from db.database import Database
from product.first_run import (
    FirstRunMemory,
    FirstRunPayload,
    apply_first_run_setup,
    first_run_result_to_dict,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run first-use setup in one command")
    parser.add_argument("--name", help="Preferred user name")
    parser.add_argument("--university")
    parser.add_argument("--program")
    parser.add_argument("--timezone")
    parser.add_argument("--locale")
    parser.add_argument("--wifi-ssid")
    parser.add_argument("--wifi-password", help="Used only if --apply-wifi is set; never stored")
    parser.add_argument("--apply-wifi", action="store_true")
    parser.add_argument("--whatsapp-number")
    parser.add_argument("--trusted-contact-name")
    parser.add_argument("--trusted-contact-phone")
    parser.add_argument("--wellbeing-unit-name")
    parser.add_argument("--wellbeing-unit-phone")
    parser.add_argument("--enable-whatsapp", action="store_true")
    parser.add_argument("--enable-progress", action="store_true")
    parser.add_argument("--enable-proactive", action="store_true")
    parser.add_argument("--enable-sensitive-memory", action="store_true")
    parser.add_argument("--enable-wellbeing", action="store_true")
    parser.add_argument("--enable-contact-alerts", action="store_true")
    parser.add_argument("--serial")
    parser.add_argument("--lot")
    parser.add_argument("--assigned-user-label")
    parser.add_argument(
        "--memory",
        action="append",
        default=[],
        help="Editable normal memory, repeatable.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    settings = Settings()
    db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
    try:
        result = apply_first_run_setup(db, settings, _payload_from_args(args))
    finally:
        db.close()

    payload = first_run_result_to_dict(result)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Rako first-run completo.")
        print(f"Ready: {payload['ready']}")
        print(f"Memorias agregadas: {payload['memories_added']}")
        for action in payload["next_actions"]:
            print(f"- {action}")
    return 0 if result.ready else 2


def _payload_from_args(args: argparse.Namespace) -> FirstRunPayload:
    return FirstRunPayload(
        profile={
            "preferred_name": args.name,
            "university": args.university,
            "program": args.program,
            "timezone": args.timezone,
            "locale": args.locale,
        },
        consent={
            "whatsapp_enabled": args.enable_whatsapp,
            "progress_reports_enabled": args.enable_progress,
            "proactive_messages_enabled": args.enable_proactive,
            "sensitive_memory_enabled": args.enable_sensitive_memory,
            "wellbeing_escalation_enabled": args.enable_wellbeing,
            "trusted_contact_alerts_enabled": args.enable_contact_alerts,
        },
        channels={
            "wifi_ssid": args.wifi_ssid,
            "whatsapp_number": args.whatsapp_number,
            "trusted_contact_name": args.trusted_contact_name,
            "trusted_contact_phone": args.trusted_contact_phone,
            "wellbeing_unit_name": args.wellbeing_unit_name,
            "wellbeing_unit_phone": args.wellbeing_unit_phone,
        },
        memories=tuple(FirstRunMemory(text=memory) for memory in args.memory),
        wifi_password=args.wifi_password,
        apply_wifi=args.apply_wifi,
        serial=args.serial,
        lot=args.lot,
        assigned_user_label=args.assigned_user_label,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
