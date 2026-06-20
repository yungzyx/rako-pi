"""WiFi setup boundary for first-run onboarding.

Rako stores only the SSID in local user config. The password is accepted only for
an immediate NetworkManager call when WiFi applying is explicitly enabled.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

from db.database import Database
from product.user_config import UserConfigService

WiFiSetupStatus = Literal["stored", "connected", "blocked", "failed"]
CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class WiFiSetupResult:
    status: WiFiSetupStatus
    ssid: str
    applied: bool
    detail: str


class WiFiSetupService:
    def __init__(
        self,
        db: Database,
        *,
        apply_enabled: bool,
        runner: CommandRunner | None = None,
    ) -> None:
        self._db = db
        self._apply_enabled = apply_enabled
        self._runner = runner or _run_nmcli

    def configure(
        self,
        *,
        ssid: str,
        password: str | None = None,
        apply: bool = False,
    ) -> WiFiSetupResult:
        clean_ssid = " ".join(ssid.strip().split())[:64]
        if not clean_ssid:
            raise ValueError("ssid cannot be empty")

        UserConfigService(self._db).update_channels({"wifi_ssid": clean_ssid})

        if not apply:
            return WiFiSetupResult(
                status="stored",
                ssid=clean_ssid,
                applied=False,
                detail="SSID stored for onboarding. WiFi was not changed.",
            )
        if not self._apply_enabled:
            return WiFiSetupResult(
                status="blocked",
                ssid=clean_ssid,
                applied=False,
                detail="WiFi apply is disabled. Set RAKO_WIFI_APPLY_ENABLED=1 to allow nmcli.",
            )
        if not password:
            return WiFiSetupResult(
                status="blocked",
                ssid=clean_ssid,
                applied=False,
                detail="Password is required to apply WiFi, and it will not be stored.",
            )

        try:
            self._runner(("nmcli", "device", "wifi", "connect", clean_ssid, "password", password))
        except (OSError, subprocess.SubprocessError) as exc:
            return WiFiSetupResult(
                status="failed",
                ssid=clean_ssid,
                applied=False,
                detail=f"NetworkManager failed: {exc}",
            )
        return WiFiSetupResult(
            status="connected",
            ssid=clean_ssid,
            applied=True,
            detail="NetworkManager accepted the WiFi configuration.",
        )


def wifi_setup_result_to_dict(result: WiFiSetupResult) -> dict[str, Any]:
    return asdict(result)


def _run_nmcli(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
