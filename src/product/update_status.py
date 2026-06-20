"""Read-only software update status.

The production-safe first step is observability: every unit should report the
build it is running and the release channel it follows. Applying OTA updates is
kept out of this module until signing and rollback are implemented.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

ReleaseChannel = Literal["stable", "beta", "dev"]


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    app_version: str
    build_sha: str | None
    release_channel: ReleaseChannel
    update_apply_enabled: bool
    update_available: bool
    source: str
    detail: str


def build_update_status(*, repo_root: Path | None = None) -> UpdateStatus:
    channel = _release_channel(os.getenv("RAKO_RELEASE_CHANNEL", "stable"))
    build_sha = os.getenv("RAKO_BUILD_SHA") or _git_sha(repo_root)
    return UpdateStatus(
        app_version=current_app_version(repo_root=repo_root),
        build_sha=build_sha,
        release_channel=channel,
        update_apply_enabled=False,
        update_available=False,
        source="local",
        detail=(
            "Read-only status. OTA apply requires signed releases and rollback before "
            "it should run on student devices."
        ),
    )


def update_status_to_dict(status: UpdateStatus) -> dict[str, Any]:
    return asdict(status)


def current_app_version(*, repo_root: Path | None = None) -> str:
    try:
        return metadata.version("rako-pi")
    except metadata.PackageNotFoundError:
        pass
    root = repo_root or Path(__file__).resolve().parents[2]
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return "0.0.0"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version ="):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


def _release_channel(value: str) -> ReleaseChannel:
    if value in {"stable", "beta", "dev"}:
        return value  # type: ignore[return-value]
    return "stable"


def _git_sha(repo_root: Path | None) -> str | None:
    root = repo_root or Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = result.stdout.strip()
    return sha or None
