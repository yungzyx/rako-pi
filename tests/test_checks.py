"""Tests for the local/CI quality harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_checks_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "checks.py"
    spec = importlib.util.spec_from_file_location("rako_checks", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hygiene_fails_on_stale_markers(tmp_path: Path) -> None:
    checks = _load_checks_module()
    stale_marker = chr(40) + "TODO" + chr(41)
    (tmp_path / "src").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "README.md").write_text(
        f"pendiente {stale_marker}\n",
        encoding="utf-8",
    )
    (tmp_path / "PRODUCT_JOURNEY.md").write_text("", encoding="utf-8")
    (tmp_path / "PRODUCTION_PLAN.md").write_text("", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(
        "\n".join(checks.REQUIRED_GITIGNORE_PATTERNS),
        encoding="utf-8",
    )

    violations = checks._find_hygiene_violations(tmp_path)

    assert violations == [f"README.md:1: stale marker {stale_marker!r}"]


def test_hygiene_fails_when_required_gitignore_pattern_is_missing(tmp_path: Path) -> None:
    checks = _load_checks_module()
    for target in checks.HYGIENE_TARGETS:
        path = tmp_path / target
        if "." in target:
            path.write_text("", encoding="utf-8")
        else:
            path.mkdir()
    patterns = [pattern for pattern in checks.REQUIRED_GITIGNORE_PATTERNS if pattern != "secrets/"]
    (tmp_path / ".gitignore").write_text("\n".join(patterns), encoding="utf-8")

    violations = checks._find_hygiene_violations(tmp_path)

    assert violations == [".gitignore missing required pattern 'secrets/'"]


def test_hygiene_passes_for_clean_repo_shape(tmp_path: Path) -> None:
    checks = _load_checks_module()
    for target in checks.HYGIENE_TARGETS:
        path = tmp_path / target
        if "." in target:
            path.write_text("ok\n", encoding="utf-8")
        else:
            path.mkdir()
            (path / "file.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(
        "\n".join(checks.REQUIRED_GITIGNORE_PATTERNS),
        encoding="utf-8",
    )

    assert checks._find_hygiene_violations(tmp_path) == []


def test_stress_runs_repeated_target_cycles(monkeypatch: Any) -> None:
    checks = _load_checks_module()
    calls: list[tuple[str, ...]] = []
    hygiene_runs = 0

    def fake_hygiene() -> None:
        nonlocal hygiene_runs
        hygiene_runs += 1

    def fake_run(command: tuple[str, ...]) -> None:
        calls.append(command)

    monkeypatch.setattr(checks, "_run_hygiene", fake_hygiene)
    monkeypatch.setattr(checks, "_run", fake_run)

    assert checks.main(["stress", "--stress-runs", "2"]) == 0

    assert hygiene_runs == 1
    assert len(calls) == 2
    assert all(command[1:4] == ("-m", "pytest", "-q") for command in calls)
    assert all("--maxfail=1" in command for command in calls)
    assert all("tests/mobile" in command for command in calls)


def test_stress_rejects_non_positive_repetitions() -> None:
    checks = _load_checks_module()

    try:
        checks._run_stress(repetitions=0)
    except SystemExit as exc:
        assert str(exc) == "--stress-runs must be >= 1"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("stress should reject non-positive repetitions")
