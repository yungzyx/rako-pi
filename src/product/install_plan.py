"""Dry-run installation plan for turning a flashed Pi into a Rako unit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from config import Settings

InstallStepStatus = Literal["ready", "manual", "blocked"]


@dataclass(frozen=True, slots=True)
class InstallStep:
    name: str
    status: InstallStepStatus
    command: str
    detail: str


@dataclass(frozen=True, slots=True)
class InstallPlan:
    ready_to_run: bool
    steps: tuple[InstallStep, ...]


def build_install_plan(settings: Settings) -> InstallPlan:
    steps = (
        _step(
            "system packages",
            "ready",
            "sudo apt update && sudo apt install -y python3.12 python3.12-venv sqlcipher libsqlcipher-dev portaudio19-dev libsndfile1 ffmpeg",
            "Base packages for Python, SQLCipher, audio and media.",
        ),
        _step(
            "python environment",
            "ready",
            "python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt",
            "Creates local virtualenv and installs runtime dependencies.",
        ),
        _step(
            "audio profile",
            "manual",
            "./scripts/setup_respeaker_audio.sh",
            "Applies ReSpeaker capture/playback tuning; run on physical board.",
        ),
        _step(
            "systemd api",
            "ready",
            "sudo cp systemd/rako-api.service /etc/systemd/system/rako-api.service",
            "Installs local API service definition.",
        ),
        _step(
            "systemd chat",
            "ready",
            "sudo cp systemd/rako-chat.service /etc/systemd/system/rako-chat.service",
            "Installs physical chat service definition.",
        ),
        _step(
            "enable services",
            "manual",
            "sudo systemctl daemon-reload && sudo systemctl enable --now rako-api rako-chat",
            "Enable only after .env, audio and OLED are checked.",
        ),
        _step(
            "security env",
            "ready" if settings.rako_api_token and settings.sqlite_encryption_key else "blocked",
            "./scripts/rako-factory-image --serial SN --lot LOT --write-env .env.generated",
            "Generate per-board token and SQLite key before production handoff.",
        ),
    )
    return InstallPlan(
        ready_to_run=all(step.status != "blocked" for step in steps),
        steps=steps,
    )


def install_plan_to_dict(plan: InstallPlan) -> dict[str, Any]:
    return {
        "ready_to_run": plan.ready_to_run,
        "steps": [asdict(step) for step in plan.steps],
    }


def _step(name: str, status: InstallStepStatus, command: str, detail: str) -> InstallStep:
    return InstallStep(name=name, status=status, command=command, detail=detail)
