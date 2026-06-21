"""Read-only software update status and OTA planning.

Rako can now evaluate a release manifest and produce an update plan. Applying
the update remains disabled until signed artifacts, atomic install, and rollback
are wired end-to-end on real devices.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from config import Settings

ReleaseChannel = Literal["stable", "beta", "dev"]
UpdateDecision = Literal["up_to_date", "available", "blocked", "not_configured", "invalid"]


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    app_version: str
    build_sha: str | None
    release_channel: ReleaseChannel
    update_apply_enabled: bool
    update_available: bool
    source: str
    detail: str


@dataclass(frozen=True, slots=True)
class UpdateManifest:
    version: str
    channel: ReleaseChannel
    artifact_url: str
    artifact_sha256: str
    rollback_version: str | None
    minimum_version: str | None
    release_notes: str | None


@dataclass(frozen=True, slots=True)
class UpdatePlan:
    decision: UpdateDecision
    current_version: str
    target_version: str | None
    release_channel: ReleaseChannel
    update_apply_enabled: bool
    steps: tuple[str, ...]
    reasons: tuple[str, ...]
    manifest: UpdateManifest | None


def build_update_status(
    settings: Settings | None = None,
    *,
    repo_root: Path | None = None,
) -> UpdateStatus:
    settings = settings or Settings()
    channel = _release_channel(settings.rako_release_channel)
    build_sha = _git_sha(repo_root)
    manifest = load_update_manifest(settings)
    current_version = current_app_version(repo_root=repo_root)
    update_available = (
        manifest is not None
        and manifest.channel == channel
        and _compare_versions(manifest.version, current_version) > 0
    )
    return UpdateStatus(
        app_version=current_version,
        build_sha=build_sha,
        release_channel=channel,
        update_apply_enabled=settings.rako_update_apply_enabled,
        update_available=update_available,
        source="manifest" if manifest is not None else "local",
        detail=(
            "Update apply is disabled by default. A manifest can be evaluated, but install "
            "requires signed releases, healthcheck, and rollback."
        ),
    )


def update_status_to_dict(status: UpdateStatus) -> dict[str, Any]:
    return asdict(status)


def build_update_plan(
    settings: Settings,
    *,
    repo_root: Path | None = None,
) -> UpdatePlan:
    channel = _release_channel(settings.rako_release_channel)
    current_version = current_app_version(repo_root=repo_root)
    manifest = load_update_manifest(settings)
    if manifest is None:
        return UpdatePlan(
            decision="not_configured",
            current_version=current_version,
            target_version=None,
            release_channel=channel,
            update_apply_enabled=settings.rako_update_apply_enabled,
            steps=(),
            reasons=("No update manifest configured.",),
            manifest=None,
        )
    reasons = _manifest_blockers(manifest, channel=channel, current_version=current_version)
    if reasons:
        return UpdatePlan(
            decision="blocked",
            current_version=current_version,
            target_version=manifest.version,
            release_channel=channel,
            update_apply_enabled=settings.rako_update_apply_enabled,
            steps=(),
            reasons=reasons,
            manifest=manifest,
        )
    if _compare_versions(manifest.version, current_version) <= 0:
        return UpdatePlan(
            decision="up_to_date",
            current_version=current_version,
            target_version=manifest.version,
            release_channel=channel,
            update_apply_enabled=settings.rako_update_apply_enabled,
            steps=(),
            reasons=("Current version is already up to date.",),
            manifest=manifest,
        )
    return UpdatePlan(
        decision="available",
        current_version=current_version,
        target_version=manifest.version,
        release_channel=channel,
        update_apply_enabled=settings.rako_update_apply_enabled,
        steps=(
            "Download artifact to a staging directory.",
            "Verify artifact SHA-256 before unpacking.",
            "Stop user-facing services only after a clean health precheck.",
            "Install into an inactive release directory.",
            "Run rako-doctor and test imports against the staged release.",
            "Switch the active release atomically.",
            "Restart services and record heartbeat.",
            "Rollback to previous release if healthcheck fails.",
        ),
        reasons=(
            "Update is available, but automatic apply remains gated by RAKO_UPDATE_APPLY_ENABLED.",
        ),
        manifest=manifest,
    )


def update_plan_to_dict(plan: UpdatePlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["steps"] = list(plan.steps)
    payload["reasons"] = list(plan.reasons)
    return payload


def load_update_manifest(settings: Settings) -> UpdateManifest | None:
    if not settings.rako_update_manifest_path:
        return None
    path = Path(settings.rako_update_manifest_path).expanduser()
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return parse_update_manifest(payload)


def parse_update_manifest(payload: dict[str, Any]) -> UpdateManifest | None:
    version = _clean_required_text(payload.get("version"))
    artifact_url = _clean_required_text(payload.get("artifact_url"))
    artifact_sha256 = _clean_required_text(payload.get("artifact_sha256"))
    channel = _release_channel(str(payload.get("channel", "stable")))
    if not version or not artifact_url or not _valid_sha256(artifact_sha256):
        return None
    return UpdateManifest(
        version=version,
        channel=channel,
        artifact_url=artifact_url,
        artifact_sha256=artifact_sha256.lower(),
        rollback_version=_clean_optional_text(payload.get("rollback_version")),
        minimum_version=_clean_optional_text(payload.get("minimum_version")),
        release_notes=_clean_optional_text(payload.get("release_notes")),
    )


def artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _manifest_blockers(
    manifest: UpdateManifest,
    *,
    channel: ReleaseChannel,
    current_version: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if manifest.channel != channel:
        reasons.append(
            f"Manifest channel {manifest.channel} does not match device channel {channel}."
        )
    if (
        manifest.minimum_version
        and _compare_versions(current_version, manifest.minimum_version) < 0
    ):
        reasons.append(
            f"Current version {current_version} is older than minimum {manifest.minimum_version}."
        )
    return tuple(reasons)


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    if left_parts > right_parts:
        return 1
    if left_parts < right_parts:
        return -1
    return 0


def _version_parts(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in value.replace("-", ".").split("."):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts or [0])


def _valid_sha256(value: str | None) -> bool:
    return (
        bool(value) and len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value)
    )


def _clean_required_text(value: object) -> str | None:
    text = _clean_optional_text(value)
    return text or None


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


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
