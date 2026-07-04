#!/usr/bin/env python3
"""Project quality harness.

This is the single entry point for local checks and GitHub Actions. Keep CI and
developer commands in sync by adding new quality gates here first.
"""

from __future__ import annotations

import argparse
import ast
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
    "tests/test_safety_scope.py",
    "tests/test_safety_triage.py",
    "tests/test_emotion_types.py",
    "tests/test_db_journal.py",
    # Estos no testean el detector en sí, sino que el veto de crisis está
    # realmente cableado antes del LLM en cada punto de entrada real
    # (orquestador, loop de voz, canal WhatsApp) — un fallo aquí significa
    # que el bypass de crisis puede regresionar sin que el fixture puro lo
    # note.
    "tests/test_orchestrator.py",
    "tests/test_orchestrator_run.py",
    "tests/channels/whatsapp/test_whatsapp_service.py",
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
    ".github",
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

MAX_FILE_LINES = 800
MAX_FUNCTION_LINES = 50

# CLAUDE.md exige <=800 líneas/archivo. `mobile/api.py` ya lo viola — queda
# aquí hasta que el refactor a `src/mobile/routes/` (routers por dominio)
# aterrice. No agregar archivos nuevos a esta lista: un archivo nuevo que
# viole el máximo debe partirse, no listarse acá.
GRANDFATHERED_OVERSIZED_FILES: frozenset[str] = frozenset(
    {
        "src/mobile/api.py",
        # Cruzó el máximo por los fixes de privacidad P0.4/P0.5 (filtro de
        # sensibilidad de memoria, autenticación de remitente, registro en
        # crisis_journal). Pendiente de partir junto con sus funciones largas
        # (ver GRANDFATHERED_LONG_FUNCTIONS) en el refactor de P2.
        "src/channels/whatsapp/service.py",
    }
)

# CLAUDE.md exige <50 líneas/función. Estas son violaciones preexistentes,
# de antes de que este chequeo existiera. No agregar funciones nuevas a esta
# lista: una función nueva que viole el máximo debe partirse, no listarse acá.
GRANDFATHERED_LONG_FUNCTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("src/bootstrap.py", "build_dev_application"),
        ("src/bootstrap.py", "build_pi_application"),
        ("src/channels/whatsapp/service.py", "_handle_config_command"),
        ("src/channels/whatsapp/service.py", "_handle_memory_command"),
        ("src/channels/whatsapp/service.py", "_handle_menu_choice"),
        ("src/channels/whatsapp/service.py", "_handle_pending"),
        ("src/channels/whatsapp/service.py", "_handle_pending_focus"),
        ("src/channels/whatsapp/service.py", "handle_inbound"),
        ("src/main.py", "cli"),
        ("src/mobile/api.py", "create_app"),
        ("src/mobile/factory_page.py", "render_factory_page"),
        ("src/product/factory_acceptance.py", "build_factory_acceptance_checklist"),
        ("src/product/first_run.py", "apply_first_run_setup"),
        ("src/product/hotspot_setup.py", "start"),
        ("src/product/install_runner.py", "execute_install_plan"),
        ("src/product/pilot_plan.py", "build_pilot_plan"),
        ("src/product/provisioning_plan.py", "build_provisioning_plan"),
        ("src/product/setup_flow.py", "build_setup_flow"),
        ("src/product/update_status.py", "build_update_plan"),
        ("src/productivity/coaching.py", "build_coaching_recommendation"),
        ("src/productivity/focus.py", "_extract_task_title"),
        ("src/productivity/study_plan.py", "build_study_plan"),
        ("src/safety/detector.py", "detect_crisis"),
    }
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
    violations.extend(_find_file_size_violations(repo_root))
    violations.extend(_find_function_length_violations(repo_root))
    return violations


def _find_file_size_violations(repo_root: Path) -> list[str]:
    violations: list[str] = []
    src_dir = repo_root / "src"
    if not src_dir.is_dir():
        return violations
    for path in sorted(src_dir.rglob("*.py")):
        rel_path = path.relative_to(repo_root).as_posix()
        if rel_path in GRANDFATHERED_OVERSIZED_FILES:
            continue
        line_count = sum(1 for _ in path.open(encoding="utf-8"))
        if line_count > MAX_FILE_LINES:
            violations.append(f"{rel_path}: {line_count} lines (max {MAX_FILE_LINES})")
    return violations


def _find_function_length_violations(repo_root: Path) -> list[str]:
    violations: list[str] = []
    src_dir = repo_root / "src"
    if not src_dir.is_dir():
        return violations
    for path in sorted(src_dir.rglob("*.py")):
        rel_path = path.relative_to(repo_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            end_lineno = node.end_lineno
            if end_lineno is None:
                continue
            length = end_lineno - node.lineno + 1
            if length <= MAX_FUNCTION_LINES:
                continue
            if (rel_path, node.name) in GRANDFATHERED_LONG_FUNCTIONS:
                continue
            violations.append(
                f"{rel_path}:{node.lineno}: {node.name} is {length} lines "
                f"(max {MAX_FUNCTION_LINES})"
            )
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
