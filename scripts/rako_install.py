#!/usr/bin/env python3
"""Dry-run/apply installer for Rako production setup steps."""

from __future__ import annotations

import argparse
import json
import sys

from config import Settings
from product.install_plan import build_install_plan, install_plan_to_dict
from product.install_runner import execute_install_plan, install_execution_to_dict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review or apply Rako installation steps")
    parser.add_argument("--apply", action="store_true", help="Execute ready steps")
    parser.add_argument("--step", help="Run only one named step, for example 'systemd api'")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    settings = Settings()
    plan = build_install_plan(settings)
    execution = execute_install_plan(settings, apply=args.apply, step=args.step)
    payload = {
        "plan": install_plan_to_dict(plan),
        "execution": install_execution_to_dict(execution),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)

    if execution.status in {"blocked", "failed"}:
        return 2
    return 0


def _print_human(payload: dict[str, object]) -> None:
    plan = payload["plan"]
    execution = payload["execution"]
    assert isinstance(plan, dict)
    assert isinstance(execution, dict)
    print("Rako install plan")
    print(f"Ready to run: {plan['ready_to_run']}")
    print(f"Execution: {execution['status']}")
    print("")
    for step in plan["steps"]:
        print(f"- {step['name']} [{step['status']}]")
        print(f"  {step['command']}")
        print(f"  {step['detail']}")
    if execution["blocked"]:
        print("")
        print("Bloqueado:")
        for item in execution["blocked"]:
            print(f"- {item}")
    if execution["executed"]:
        print("")
        print("Ejecutado:")
        for item in execution["executed"]:
            print(f"- {item}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
