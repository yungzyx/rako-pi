#!/usr/bin/env python3
"""Project quality harness.

This is the single entry point for local checks and GitHub Actions. Keep CI and
developer commands in sync by adding new quality gates here first.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence

RUFF_TARGETS: tuple[str, ...] = (
    "src",
    "tests",
    "eyes.py",
    "scripts/button_conversation.py",
    "scripts/chat_text.py",
    "scripts/focus_countdown.py",
    "scripts/focus_timer.py",
    "scripts/listen_wake_word.py",
    "scripts/music_mode.py",
    "scripts/rako_demo.py",
    "scripts/rako_demo_mode.py",
    "scripts/rako_doctor.py",
    "scripts/rako_first_run.py",
    "scripts/rako_provision.py",
    "scripts/rako_install.py",
    "scripts/rako_support_bundle.py",
    "scripts/reindex_rag.py",
    "scripts/test_tts.py",
    "scripts/checks.py",
)

SAFETY_TESTS: tuple[str, ...] = (
    "tests/test_safety_detector.py",
    "tests/test_safety_protocol.py",
    "tests/test_safety_responses.py",
    "tests/test_safety_resources.py",
    "tests/test_safety_protocol_with_journal.py",
    "tests/test_emotion_types.py",
    "tests/test_db_journal.py",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Rako quality checks")
    parser.add_argument(
        "command",
        choices=("lint", "test", "safety", "all"),
        help="Check group to run",
    )
    args = parser.parse_args(argv)

    if args.command in {"lint", "all"}:
        _run_lint()
    if args.command in {"test", "all"}:
        _run_tests()
    if args.command in {"safety", "all"}:
        _run_safety()
    return 0


def _run_lint() -> None:
    _run((sys.executable, "-m", "ruff", "check", *RUFF_TARGETS))
    _run((sys.executable, "-m", "ruff", "format", "--check", *RUFF_TARGETS))


def _run_tests() -> None:
    _run(
        (
            sys.executable,
            "-m",
            "pytest",
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=95",
        )
    )


def _run_safety() -> None:
    _run((sys.executable, "-m", "pytest", "-v", *SAFETY_TESTS))


def _run(command: Sequence[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
