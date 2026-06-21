#!/usr/bin/env python3
"""Print safe demo mode commands and script."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from product.demo_mode import build_demo_mode, demo_mode_to_dict  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show safe Rako demo mode")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = demo_mode_to_dict(build_demo_mode())
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Rako demo seguro")
        print("Comandos:")
        for command in payload["commands"]:
            print(f"- {command}")
        print("Guion:")
        for line in payload["script"]:
            print(f"- {line}")
        print("Notas:")
        for note in payload["safety_notes"]:
            print(f"- {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
