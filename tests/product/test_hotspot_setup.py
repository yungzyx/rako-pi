from __future__ import annotations

from config import Settings
from product.hotspot_setup import build_hotspot_plan, hotspot_plan_to_dict


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
