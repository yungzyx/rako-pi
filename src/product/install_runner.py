"""Safe executor for the dry-run installation plan."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

from config import Settings
from product.install_plan import InstallStep, build_install_plan

InstallExecutionStatus = Literal["dry_run", "applied", "blocked", "failed"]
ShellRunner = Callable[[str], subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class InstallExecution:
    status: InstallExecutionStatus
    apply: bool
    executed: tuple[str, ...]
    skipped: tuple[str, ...]
    blocked: tuple[str, ...]
    errors: tuple[str, ...]


def execute_install_plan(
    settings: Settings,
    *,
    apply: bool = False,
    step: str | None = None,
    runner: ShellRunner | None = None,
) -> InstallExecution:
    plan = build_install_plan(settings)
    selected = tuple(_matching_steps(plan.steps, step))
    executable = tuple(item for item in selected if item.status == "ready")
    blocked = tuple(item.name for item in selected if item.status == "blocked")
    skipped = tuple(item.name for item in selected if item.status == "manual")

    if step and not selected:
        return InstallExecution(
            status="blocked",
            apply=apply,
            executed=(),
            skipped=(),
            blocked=(f"unknown step: {step}",),
            errors=(),
        )

    if not apply:
        return InstallExecution(
            status="dry_run",
            apply=False,
            executed=(),
            skipped=tuple(item.name for item in selected if item.status != "ready"),
            blocked=blocked,
            errors=(),
        )

    if blocked:
        return InstallExecution(
            status="blocked",
            apply=True,
            executed=(),
            skipped=skipped,
            blocked=blocked,
            errors=(),
        )

    shell_runner = runner or _run_shell
    executed: list[str] = []
    errors: list[str] = []
    for item in executable:
        try:
            shell_runner(item.command)
            executed.append(item.name)
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"{item.name}: {exc}")
            break

    status: InstallExecutionStatus = "failed" if errors else "applied"
    return InstallExecution(
        status=status,
        apply=True,
        executed=tuple(executed),
        skipped=skipped,
        blocked=blocked,
        errors=tuple(errors),
    )


def install_execution_to_dict(execution: InstallExecution) -> dict[str, Any]:
    payload = asdict(execution)
    return {
        key: list(value) if isinstance(value, tuple) else value for key, value in payload.items()
    }


def _matching_steps(steps: tuple[InstallStep, ...], name: str | None) -> list[InstallStep]:
    if not name:
        return list(steps)
    clean = name.strip().lower()
    return [step for step in steps if step.name.lower() == clean]


def _run_shell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        shell=True,
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
