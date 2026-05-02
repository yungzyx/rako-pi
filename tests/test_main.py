"""Tests del CLI — smoke tests de los subcomandos."""

from __future__ import annotations

from pathlib import Path

import pytest

import main as cli_module


def _common_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path / "missing-vault"))
    monkeypatch.setenv("RAKO_ENV", "dev")


def test_demo_turn_prints_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    exit_code = cli_module.cli(["demo-turn", "me siento atascado"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Estoy" in captured.out or "Aquí" in captured.out or "Rako" in captured.out


def test_demo_crisis_panic_invokes_protocol(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    exit_code = cli_module.cli(["demo-crisis-panic"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "crisis" in captured.out.lower() or "protocolo" in captured.out.lower()
    assert "PANIC_BUTTON" in captured.out or "panic" in captured.out.lower()


def test_purge_all_clears_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    # Sembrar algo primero.
    cli_module.cli(["demo-crisis-panic"])
    capsys.readouterr()

    exit_code = cli_module.cli(["purge-all"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "borrado" in captured.out.lower() or "deleted" in captured.out.lower() or "purg" in captured.out.lower()


def test_help_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_module.cli(["--help"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "demo-turn" in captured.out


def test_unknown_subcommand_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_module.cli(["nonexistent-command"])

    assert exc.value.code != 0
