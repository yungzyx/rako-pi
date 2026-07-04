from __future__ import annotations

import subprocess

from config import Settings
from product.install_runner import execute_install_plan


def test_install_runner_is_dry_run_by_default() -> None:
    settings = Settings(rako_api_token="token", sqlite_encryption_key="key")
    calls: list[str] = []

    result = execute_install_plan(settings, runner=lambda command: _record(calls, command))

    assert result.status == "dry_run"
    assert result.executed == ()
    assert calls == []


def test_install_runner_applies_only_ready_steps() -> None:
    settings = Settings(rako_api_token="token", sqlite_encryption_key="key")
    calls: list[str] = []

    result = execute_install_plan(
        settings,
        apply=True,
        step="systemd api",
        runner=lambda command: _record(calls, command),
    )

    assert result.status == "applied"
    assert result.executed == ("systemd api",)
    assert calls == ["./scripts/install_systemd.sh --no-enable rako-api"]


def test_install_runner_blocks_missing_security_env() -> None:
    settings = Settings(rako_api_token=None, sqlite_encryption_key=None)

    result = execute_install_plan(settings, apply=True, step="security env")

    assert result.status == "blocked"
    assert result.blocked == ("security env",)


def _record(calls: list[str], command: str) -> subprocess.CompletedProcess[str]:
    calls.append(command)
    return subprocess.CompletedProcess(command, 0, "", "")
