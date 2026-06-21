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
from pathlib import Path

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

STRESS_TEST_TARGETS: tuple[str, ...] = (
    "tests/channels/whatsapp",
    "tests/mobile",
    "tests/product",
    "tests/productivity",
    "tests/test_hardware_event_bus.py",
    "tests/test_hardware_oled_runtime.py",
    "tests/test_main.py",
    "tests/test_orchestrator.py",
    "tests/test_orchestrator_run.py",
    "tests/test_sync_coordinator.py",
    "tests/test_sync_queue.py",
    "tests/test_voice_stt.py",
    "tests/test_voice_tts.py",
    "tests/test_voice_wake_audio.py",
)

HYGIENE_MARKERS: tuple[str, ...] = (
    "TODO " + "completo",
    chr(40) + "TODO" + chr(41),
    "FIX" + "ME",
    "X" * 3,
    "HA" + "CK",
)

HYGIENE_TARGETS: tuple[str, ...] = (
    "README.md",
    "PRODUCT_JOURNEY.md",
    "PRODUCTION_PLAN.md",
    "src",
    "scripts",
    "tests",
)

REQUIRED_GITIGNORE_PATTERNS: tuple[str, ...] = (
    ".env",
    "secrets/",
    "data/",
    "chroma_db/",
    "coverage.xml",
    "tmp-*.dts",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Rako quality checks")
    parser.add_argument(
        "command",
        choices=("lint", "test", "safety", "hygiene", "stress", "all"),
        help="Check group to run",
    )
    parser.add_argument(
        "--stress-runs",
        type=int,
        default=3,
        help="Number of repeated stress cycles for the stress command.",
    )
    args = parser.parse_args(argv)

    if args.command in {"lint", "all"}:
        _run_lint()
    if args.command in {"test", "all"}:
        _run_tests()
    if args.command in {"safety", "all"}:
        _run_safety()
    if args.command in {"hygiene", "all"}:
        _run_hygiene()
    if args.command == "stress":
        _run_stress(repetitions=args.stress_runs)
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


def _run_hygiene() -> None:
    violations = _find_hygiene_violations(Path.cwd())
    if violations:
        print("Hygiene check failed:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        raise SystemExit(1)
    print("Hygiene check passed")


def _run_stress(*, repetitions: int) -> None:
    if repetitions < 1:
        raise SystemExit("--stress-runs must be >= 1")
    _run_hygiene()
    for index in range(1, repetitions + 1):
        print(f"Stress cycle {index}/{repetitions}", flush=True)
        _run(
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--maxfail=1",
                *STRESS_TEST_TARGETS,
            )
        )


def _find_hygiene_violations(repo_root: Path) -> list[str]:
    violations: list[str] = []
    violations.extend(_find_stale_markers(repo_root))
    violations.extend(_find_missing_gitignore_patterns(repo_root))
    return violations


def _find_stale_markers(repo_root: Path) -> list[str]:
    violations: list[str] = []
    for target in HYGIENE_TARGETS:
        path = repo_root / target
        if path.is_file():
            _scan_text_file(path, repo_root, violations)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and "__pycache__" not in child.parts:
                    _scan_text_file(child, repo_root, violations)
    return violations


def _scan_text_file(path: Path, repo_root: Path, violations: list[str]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return
    for line_no, line in enumerate(lines, start=1):
        for marker in HYGIENE_MARKERS:
            if marker in line:
                rel_path = path.relative_to(repo_root)
                violations.append(f"{rel_path}:{line_no}: stale marker {marker!r}")


def _find_missing_gitignore_patterns(repo_root: Path) -> list[str]:
    gitignore = repo_root / ".gitignore"
    if not gitignore.exists():
        return [".gitignore is missing"]
    patterns = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    return [
        f".gitignore missing required pattern {pattern!r}"
        for pattern in REQUIRED_GITIGNORE_PATTERNS
        if pattern not in patterns
    ]


def _run(command: Sequence[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
