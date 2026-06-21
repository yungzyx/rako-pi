"""Read-only setup hotspot planning for first-run onboarding.

This module intentionally does not start NetworkManager. It produces the
commands and checks a factory script or operator can run when hotspot setup is
explicitly enabled for a production image.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from config import Settings

HotspotPlanStatus = Literal["ready", "disabled", "needs_token"]


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


def _device_suffix(device_id: str | None) -> str:
    if not device_id:
        return "local"
    clean = "".join(ch for ch in device_id if ch.isalnum())
    return clean[-6:] or "local"


def _clean_ssid(value: str) -> str:
    clean = "-".join(part for part in value.strip().split() if part)
    clean = "".join(ch for ch in clean if ch.isalnum() or ch in {"-", "_"})
    return clean[:32] or "Rako-Setup"
