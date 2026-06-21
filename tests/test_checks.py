"""Tests for the local/CI quality harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


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
