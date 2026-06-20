from __future__ import annotations

import subprocess

from db.database import Database
from product.user_config import UserConfigService
from product.wifi_setup import WiFiSetupService


def test_wifi_setup_stores_only_ssid_when_apply_is_false(db_conn) -> None:
    db = Database(db_conn)
    service = WiFiSetupService(db, apply_enabled=False)

    result = service.configure(ssid=" Casa  principal ", password="secret", apply=False)

    assert result.status == "stored"
    assert result.applied is False
    assert result.ssid == "Casa principal"
    assert UserConfigService(db).get_channels().wifi_ssid == "Casa principal"
    assert "secret" not in db.config.get_all().get("product.channels", "")


def test_wifi_setup_blocks_nmcli_when_apply_is_disabled(db_conn) -> None:
    db = Database(db_conn)
    calls: list[tuple[str, ...]] = []
    service = WiFiSetupService(
        db,
        apply_enabled=False,
        runner=lambda command: calls.append(tuple(command)) or subprocess.CompletedProcess([], 0),
    )

    result = service.configure(ssid="Casa", password="secret", apply=True)

    assert result.status == "blocked"
    assert calls == []
    assert UserConfigService(db).get_channels().wifi_ssid == "Casa"


def test_wifi_setup_runs_nmcli_when_explicitly_enabled(db_conn) -> None:
    db = Database(db_conn)
    calls: list[tuple[str, ...]] = []

    def runner(command):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    service = WiFiSetupService(db, apply_enabled=True, runner=runner)

    result = service.configure(ssid="Casa", password="secret", apply=True)

    assert result.status == "connected"
    assert result.applied is True
    assert calls == [("nmcli", "device", "wifi", "connect", "Casa", "password", "secret")]
