"""One-shot first-run setup for a newly delivered Rako.

This module ties together the smaller onboarding pieces so a setup page, CLI,
or future app can configure a board in one request without storing secrets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from config import Settings
from db.database import Database
from product.device_registry import DeviceRegistryService, device_identity_to_dict
from product.setup_flow import build_setup_flow, setup_flow_to_dict
from product.user_config import (
    MemoryCategory,
    MemorySensitivity,
    UserConfigService,
    onboarding_status_to_dict,
)
from product.wifi_setup import WiFiSetupResult, WiFiSetupService, wifi_setup_result_to_dict


@dataclass(frozen=True, slots=True)
class FirstRunMemory:
    text: str
    category: MemoryCategory = "preference"
    sensitivity: MemorySensitivity = "normal"


@dataclass(frozen=True, slots=True)
class FirstRunPayload:
    profile: dict[str, Any]
    consent: dict[str, Any]
    channels: dict[str, Any]
    memories: tuple[FirstRunMemory, ...] = ()
    wifi_password: str | None = None
    apply_wifi: bool = False
    serial: str | None = None
    lot: str | None = None
    assigned_user_label: str | None = None


@dataclass(frozen=True, slots=True)
class FirstRunResult:
    ready: bool
    next_actions: tuple[str, ...]
    onboarding: dict[str, Any]
    setup: dict[str, Any]
    wifi: dict[str, Any] | None
    identity: dict[str, Any] | None
    memories_added: int


def apply_first_run_setup(
    db: Database,
    settings: Settings,
    payload: FirstRunPayload,
) -> FirstRunResult:
    service = UserConfigService(db)
    memories_added = 0
    wifi_result: WiFiSetupResult | None = None

    profile_patch = _clean_patch(payload.profile)
    if profile_patch:
        service.update_profile(profile_patch)

    channels_patch = _clean_patch(payload.channels)
    wifi_ssid = channels_patch.pop("wifi_ssid", None)
    if channels_patch:
        service.update_channels(channels_patch)
    if wifi_ssid:
        wifi_result = WiFiSetupService(
            db,
            apply_enabled=settings.rako_wifi_apply_enabled,
        ).configure(
            ssid=str(wifi_ssid),
            password=payload.wifi_password,
            apply=payload.apply_wifi,
        )

    consent_patch = _clean_patch(payload.consent)
    if consent_patch:
        service.update_consent(consent_patch)

    for memory in payload.memories:
        service.add_memory(
            text=memory.text,
            category=memory.category,
            sensitivity=memory.sensitivity,
        )
        memories_added += 1

    identity_payload = None
    if payload.serial or payload.lot or payload.assigned_user_label:
        identity_payload = device_identity_to_dict(
            DeviceRegistryService(db, settings).provision(
                serial=payload.serial,
                lot=payload.lot,
                assigned_user_label=payload.assigned_user_label,
            )
        )

    onboarding = onboarding_status_to_dict(service.onboarding_status())
    setup = setup_flow_to_dict(build_setup_flow(db, settings))
    next_actions = _next_actions(onboarding, setup, wifi_result)
    return FirstRunResult(
        ready=bool(onboarding["ready"]) and bool(setup["ready_for_user"]),
        next_actions=tuple(next_actions),
        onboarding=onboarding,
        setup=setup,
        wifi=wifi_setup_result_to_dict(wifi_result) if wifi_result else None,
        identity=identity_payload,
        memories_added=memories_added,
    )


def first_run_memory_to_dict(memory: FirstRunMemory) -> dict[str, Any]:
    return asdict(memory)


def first_run_result_to_dict(result: FirstRunResult) -> dict[str, Any]:
    return {
        "ready": result.ready,
        "next_actions": list(result.next_actions),
        "onboarding": result.onboarding,
        "setup": result.setup,
        "wifi": result.wifi,
        "identity": result.identity,
        "memories_added": result.memories_added,
    }


def _clean_patch(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _next_actions(
    onboarding: dict[str, Any],
    setup: dict[str, Any],
    wifi_result: WiFiSetupResult | None,
) -> list[str]:
    actions: list[str] = []
    missing = onboarding.get("missing", [])
    if missing:
        actions.append("Completar: " + ", ".join(str(item) for item in missing))
    if wifi_result and wifi_result.status in {"blocked", "failed"}:
        actions.append(wifi_result.detail)
    next_action = setup.get("next_action")
    if next_action:
        actions.append(str(next_action))
    if not actions:
        actions.append("Setup listo; ejecutar rako-doctor --factory antes de entregar.")
    return actions
