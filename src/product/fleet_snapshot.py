"""Single-device fleet snapshot for local dashboards and central sync."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import Settings
from db.database import Database
from product.device_registry import DeviceRegistryService, device_heartbeat_to_dict
from product.factory_report import build_factory_report, factory_report_to_dict
from product.hardware_validation import (
    HardwareValidationService,
    hardware_validation_summary_to_dict,
)
from product.observability import build_observability_snapshot, observability_snapshot_to_dict
from product.provisioning_plan import build_provisioning_plan, provisioning_plan_to_dict
from product.security_audit import build_security_audit, security_audit_to_dict
from product.update_status import build_update_status, update_status_to_dict


@dataclass(frozen=True, slots=True)
class FleetSnapshot:
    device_id: str
    online: bool
    app_version: str
    assignment: str | None
    heartbeat: dict[str, Any] | None
    factory: dict[str, Any]
    provisioning: dict[str, Any]
    hardware: dict[str, Any]
    security: dict[str, Any]
    update: dict[str, Any]
    observability: dict[str, Any]


def build_fleet_snapshot(
    db: Database,
    settings: Settings,
    *,
    app_version: str,
) -> FleetSnapshot:
    registry = DeviceRegistryService(db, settings)
    identity = registry.get_identity()
    heartbeat = registry.get_heartbeat()
    update = build_update_status(settings)
    return FleetSnapshot(
        device_id=identity.device_id,
        online=heartbeat is not None,
        app_version=app_version,
        assignment=identity.assigned_user_label,
        heartbeat=device_heartbeat_to_dict(heartbeat),
        factory=factory_report_to_dict(build_factory_report(db, settings, app_version=app_version)),
        provisioning=provisioning_plan_to_dict(build_provisioning_plan(db, settings)),
        hardware=hardware_validation_summary_to_dict(HardwareValidationService(db).summary()),
        security=security_audit_to_dict(build_security_audit(settings)),
        update=update_status_to_dict(update),
        observability=observability_snapshot_to_dict(build_observability_snapshot(db, settings)),
    )


def fleet_snapshot_to_dict(snapshot: FleetSnapshot) -> dict[str, Any]:
    return {
        "device_id": snapshot.device_id,
        "online": snapshot.online,
        "app_version": snapshot.app_version,
        "assignment": snapshot.assignment,
        "heartbeat": snapshot.heartbeat,
        "factory": snapshot.factory,
        "provisioning": snapshot.provisioning,
        "hardware": snapshot.hardware,
        "security": snapshot.security,
        "update": snapshot.update,
        "observability": snapshot.observability,
    }
