"""Production provisioning plan for cloning and handing off Rako boards."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from config import Settings
from db.database import Database
from product.device_registry import DEVICE_IDENTITY_KEY, DeviceRegistryService
from product.factory_acceptance import build_factory_acceptance_checklist
from product.hotspot_setup import build_hotspot_plan, hotspot_plan_to_dict
from product.setup_flow import build_setup_flow
from product.update_status import build_update_plan, update_plan_to_dict

ProvisioningStatus = Literal["ok", "warn", "fail", "manual"]


@dataclass(frozen=True, slots=True)
class ProvisioningStep:
    area: str
    name: str
    status: ProvisioningStatus
    detail: str
    action: str


@dataclass(frozen=True, slots=True)
class ProvisioningPlan:
    ready_for_image: bool
    ready_for_handoff: bool
    device_id: str | None
    release_channel: str
    hotspot: dict[str, Any]
    update: dict[str, Any]
    steps: tuple[ProvisioningStep, ...]


def build_provisioning_plan(
    db: Database,
    settings: Settings,
) -> ProvisioningPlan:
    registry = DeviceRegistryService(db, settings)
    identity = registry.get_identity()
    has_persistent_identity = bool(settings.rako_device_id or db.config.get(DEVICE_IDENTITY_KEY))
    setup = build_setup_flow(db, settings)
    acceptance = build_factory_acceptance_checklist(db, settings)
    update = build_update_plan(settings)
    hotspot = build_hotspot_plan(settings)

    steps: list[ProvisioningStep] = [
        _step(
            "identity",
            "device id",
            "ok" if has_persistent_identity else "fail",
            identity.device_id or "missing RAKO_DEVICE_ID",
            "Set a unique RAKO_DEVICE_ID before cloning or provisioning.",
        ),
        _step(
            "identity",
            "serial and lot",
            "ok" if identity.serial and identity.lot else "warn",
            f"serial={identity.serial or 'missing'}, lot={identity.lot or 'missing'}",
            "Patch /device/identity on the bench with serial, lot and assignment label.",
        ),
        _step(
            "security",
            "local api token",
            "ok" if settings.rako_env == "dev" or settings.rako_api_token else "fail",
            "configured" if settings.rako_api_token else f"{settings.rako_env} without token",
            "Generate a per-device RAKO_API_TOKEN before exposing any local API endpoint.",
        ),
        _step(
            "security",
            "sqlite encryption key",
            "ok" if settings.sqlite_encryption_key else "warn",
            "configured" if settings.sqlite_encryption_key else "missing SQLITE_ENCRYPTION_KEY",
            "Use a per-device key for production units; never reuse pilot secrets.",
        ),
        _step(
            "setup",
            "first-run hotspot",
            "ok" if hotspot.status == "ready" else "warn",
            hotspot.status,
            "Enable RAKO_SETUP_HOTSPOT_ENABLED for factory images that need phone setup.",
        ),
        _step(
            "setup",
            "onboarding flow",
            "ok" if setup.ready_for_user else "manual",
            "complete" if setup.ready_for_user else f"next step: {setup.next_step_id}",
            "Complete /setup with the student during handoff.",
        ),
        _step(
            "whatsapp",
            "cloud client",
            "ok"
            if (
                settings.whatsapp_client == "cloud"
                and settings.whatsapp_cloud_access_token
                and settings.whatsapp_cloud_phone_number_id
            )
            else "warn",
            settings.whatsapp_client,
            "Configure WhatsApp Cloud credentials for real outbound/inbound messages.",
        ),
        _step(
            "updates",
            "ota manifest",
            "ok" if update.decision in {"available", "current"} else "warn",
            update.decision,
            "Set RAKO_UPDATE_MANIFEST_PATH and public key before fleet rollout.",
        ),
        _step(
            "factory",
            "acceptance checklist",
            "ok" if acceptance.ready_for_handoff else "fail",
            (
                "ready"
                if acceptance.ready_for_handoff
                else f"{acceptance.automatic_failures} failures, "
                f"{acceptance.automatic_warnings} warnings"
            ),
            "Run rako-doctor --factory and complete manual audio/OLED/button gates.",
        ),
    ]
    blocking = [step for step in steps if step.status == "fail"]
    ready_for_image = not blocking and has_persistent_identity
    return ProvisioningPlan(
        ready_for_image=ready_for_image,
        ready_for_handoff=acceptance.ready_for_handoff and setup.ready_for_user,
        device_id=identity.device_id,
        release_channel=settings.rako_release_channel,
        hotspot=hotspot_plan_to_dict(hotspot),
        update=update_plan_to_dict(update),
        steps=tuple(steps),
    )


def provisioning_plan_to_dict(plan: ProvisioningPlan) -> dict[str, Any]:
    return {
        "ready_for_image": plan.ready_for_image,
        "ready_for_handoff": plan.ready_for_handoff,
        "device_id": plan.device_id,
        "release_channel": plan.release_channel,
        "hotspot": plan.hotspot,
        "update": plan.update,
        "steps": [asdict(step) for step in plan.steps],
    }


def _step(
    area: str,
    name: str,
    status: ProvisioningStatus,
    detail: str,
    action: str,
) -> ProvisioningStep:
    return ProvisioningStep(
        area=area,
        name=name,
        status=status,
        detail=detail,
        action=action,
    )
