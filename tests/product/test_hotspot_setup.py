from __future__ import annotations

import subprocess

from config import Settings
from product.hotspot_setup import (
    HotspotSetupService,
    build_hotspot_plan,
    hotspot_plan_to_dict,
)


def test_hotspot_plan_is_dry_run_by_default() -> None:
    settings = Settings(_env_file=None, rako_device_id="rako-unit-001")

    plan = build_hotspot_plan(settings)
    payload = hotspot_plan_to_dict(plan)

    assert payload["status"] == "disabled"
    assert payload["enabled"] is False
    assert payload["ssid"] == "Rako-Setup-nit001"
    assert "RAKO_SETUP_HOTSPOT_ENABLED" in payload["warnings"][0]
    assert "<temporary-setup-password>" in payload["commands"][1]


def test_hotspot_plan_requires_token_outside_dev() -> None:
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_device_id="rako-prod-001",
        rako_setup_hotspot_enabled=True,
        rako_api_token=None,
    )

    plan = build_hotspot_plan(settings)

    assert plan.status == "needs_token"
    assert plan.requires_api_token is True
    assert "RAKO_API_TOKEN" in plan.warnings[0]


def test_hotspot_plan_ready_when_enabled_with_token() -> None:
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_api_token="local-token",
        rako_device_id="rako-prod-001",
        rako_setup_hotspot_enabled=True,
    )

    plan = build_hotspot_plan(settings)

    assert plan.status == "ready"
    assert plan.enabled is True
    assert plan.warnings == ()


def test_hotspot_start_is_blocked_until_apply_and_password() -> None:
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_api_token="local-token",
        rako_setup_hotspot_enabled=True,
    )

    dry = HotspotSetupService(settings).start(password="temporary-123", apply=False)
    missing_password = HotspotSetupService(settings).start(apply=True)

    assert dry.status == "blocked"
    assert missing_password.status == "blocked"


def test_hotspot_start_redacts_password_with_runner() -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(list(command), 0, "", "")

    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_api_token="local-token",
        rako_setup_hotspot_enabled=True,
        rako_device_id="rako-prod-001",
    )

    result = HotspotSetupService(settings, runner=runner).start(
        password="temporary-123",
        apply=True,
    )

    assert result.status == "started"
    assert calls[0][-1] == "temporary-123"
    assert result.command is not None
    assert "temporary-123" not in result.command
    assert "<temporary-setup-password>" in result.command
