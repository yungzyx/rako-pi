"""Factory/admin report for a physical Rako unit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from config import Settings
from db.database import Database
from product.factory_acceptance import (
    acceptance_checklist_to_dict,
    build_factory_acceptance_checklist,
)
from product.setup_flow import build_setup_flow, setup_flow_to_dict


@dataclass(frozen=True, slots=True)
class FactoryReport:
    generated_at: str
    device_id: str | None
    environment: str
    app_version: str
    ready_for_handoff: bool
    setup_ready: bool
    automatic_failures: int
    automatic_warnings: int
    manual_items: int
    next_setup_step_id: str | None
    setup: dict[str, Any]
    acceptance: dict[str, Any]


def build_factory_report(
    db: Database,
    settings: Settings,
    *,
    app_version: str,
    now: datetime | None = None,
) -> FactoryReport:
    generated_at = _ensure_aware(now or datetime.now(UTC)).isoformat()
    setup = build_setup_flow(db, settings)
    acceptance = build_factory_acceptance_checklist(db, settings)
    return FactoryReport(
        generated_at=generated_at,
        device_id=settings.rako_device_id,
        environment=settings.rako_env,
        app_version=app_version,
        ready_for_handoff=acceptance.ready_for_handoff,
        setup_ready=setup.ready_for_user,
        automatic_failures=acceptance.automatic_failures,
        automatic_warnings=acceptance.automatic_warnings,
        manual_items=acceptance.manual_items,
        next_setup_step_id=setup.next_step_id,
        setup=setup_flow_to_dict(setup),
        acceptance=acceptance_checklist_to_dict(acceptance),
    )


def factory_report_to_dict(report: FactoryReport) -> dict[str, Any]:
    return asdict(report)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
