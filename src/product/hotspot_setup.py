"""Read-only setup hotspot planning for first-run onboarding.

This module intentionally does not start NetworkManager. It produces the
commands and checks a factory script or operator can run when hotspot setup is
explicitly enabled for a production image.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

from config import Settings

HotspotPlanStatus = Literal["ready", "disabled", "needs_token"]
HotspotActionStatus = Literal["started", "stopped", "blocked", "failed"]
CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class HotspotPlan:
    status: HotspotPlanStatus
    enabled: bool
    ssid: str
    interface: str
    setup_url: str
    requires_api_token: bool
    warnings: tuple[str, ...]
    commands: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HotspotActionResult:
    status: HotspotActionStatus
    ssid: str
    applied: bool
    detail: str
    command: tuple[str, ...] | None = None


class HotspotSetupService:
    def __init__(
        self,
        settings: Settings,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self._settings = settings
        self._runner = runner or _run_command

    def start(self, *, password: str | None = None, apply: bool = False) -> HotspotActionResult:
        plan = build_hotspot_plan(self._settings)
        if plan.status == "needs_token":
            return HotspotActionResult(
                status="blocked",
                ssid=plan.ssid,
                applied=False,
                detail="RAKO_API_TOKEN is required before exposing setup.",
            )
        if not self._settings.rako_setup_hotspot_enabled or not apply:
            return HotspotActionResult(
                status="blocked",
                ssid=plan.ssid,
                applied=False,
                detail="Hotspot apply is disabled. Use apply=true and RAKO_SETUP_HOTSPOT_ENABLED=1.",
            )
        if not password:
            return HotspotActionResult(
                status="blocked",
                ssid=plan.ssid,
                applied=False,
                detail="A temporary hotspot password is required and is never stored.",
            )
        command = (
            "nmcli",
            "device",
            "wifi",
            "hotspot",
            "ifname",
            plan.interface,
            "ssid",
            plan.ssid,
            "password",
            password,
        )
        try:
            self._runner(command)
        except (OSError, subprocess.SubprocessError) as exc:
            return HotspotActionResult(
                status="failed",
                ssid=plan.ssid,
                applied=False,
                detail=f"NetworkManager failed: {exc}",
                command=_redacted_command(command),
            )
        return HotspotActionResult(
            status="started",
            ssid=plan.ssid,
            applied=True,
            detail=f"Hotspot started. Open {plan.setup_url}.",
            command=_redacted_command(command),
        )

    def stop(self, *, apply: bool = False) -> HotspotActionResult:
        plan = build_hotspot_plan(self._settings)
        if not self._settings.rako_setup_hotspot_enabled or not apply:
            return HotspotActionResult(
                status="blocked",
                ssid=plan.ssid,
                applied=False,
                detail="Hotspot stop is dry-run unless apply=true and RAKO_SETUP_HOTSPOT_ENABLED=1.",
            )
        command = ("nmcli", "connection", "down", "Hotspot")
        try:
            self._runner(command)
        except (OSError, subprocess.SubprocessError) as exc:
            return HotspotActionResult(
                status="failed",
                ssid=plan.ssid,
                applied=False,
                detail=f"NetworkManager failed: {exc}",
                command=command,
            )
        return HotspotActionResult(
            status="stopped",
            ssid=plan.ssid,
            applied=True,
            detail="Hotspot connection stopped.",
            command=command,
        )


def build_hotspot_plan(settings: Settings) -> HotspotPlan:
    device_suffix = _device_suffix(settings.rako_device_id)
    ssid = _clean_ssid(f"{settings.rako_setup_hotspot_ssid_prefix}-{device_suffix}")
    warnings: list[str] = []

    if settings.rako_env != "dev" and not settings.rako_api_token:
        warnings.append("RAKO_API_TOKEN is required before exposing setup on local network.")
    if not settings.rako_setup_hotspot_enabled:
        warnings.append("RAKO_SETUP_HOTSPOT_ENABLED is disabled; plan is dry-run only.")
    if settings.rako_setup_hotspot_interface != "wlan0":
        warnings.append(
            f"Using non-default WiFi interface {settings.rako_setup_hotspot_interface}."
        )

    status: HotspotPlanStatus
    if settings.rako_env != "dev" and not settings.rako_api_token:
        status = "needs_token"
    elif settings.rako_setup_hotspot_enabled:
        status = "ready"
    else:
        status = "disabled"

    commands = (
        "# Generate a temporary password per unit; do not bake it into the image.",
        (
            "nmcli device wifi hotspot "
            f"ifname {settings.rako_setup_hotspot_interface} "
            f"ssid {ssid} password <temporary-setup-password>"
        ),
        "RAKO_API_HOST=0.0.0.0 rako-api",
        f"# Open {settings.rako_setup_hotspot_url} from the phone connected to {ssid}.",
    )
    return HotspotPlan(
        status=status,
        enabled=settings.rako_setup_hotspot_enabled,
        ssid=ssid,
        interface=settings.rako_setup_hotspot_interface,
        setup_url=settings.rako_setup_hotspot_url,
        requires_api_token=settings.rako_env != "dev",
        warnings=tuple(warnings),
        commands=commands,
    )


def hotspot_plan_to_dict(plan: HotspotPlan) -> dict[str, Any]:
    return asdict(plan)


def hotspot_action_result_to_dict(result: HotspotActionResult) -> dict[str, Any]:
    payload = asdict(result)
    if result.command is not None:
        payload["command"] = list(result.command)
    return payload


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )


def _redacted_command(command: Sequence[str]) -> tuple[str, ...]:
    redacted = list(command)
    for index, value in enumerate(redacted):
        if value == "password" and index + 1 < len(redacted):
            redacted[index + 1] = "<temporary-setup-password>"
    return tuple(redacted)


def _device_suffix(device_id: str | None) -> str:
    if not device_id:
        return "local"
    clean = "".join(ch for ch in device_id if ch.isalnum())
    return clean[-6:] or "local"


def _clean_ssid(value: str) -> str:
    clean = "-".join(part for part in value.strip().split() if part)
    clean = "".join(ch for ch in clean if ch.isalnum() or ch in {"-", "_"})
    return clean[:32] or "Rako-Setup"
