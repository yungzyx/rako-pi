"""Rutas de fábrica/operación: reportes, fleet, auditoría, hardware."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from db.database import Database
from mobile.deps import get_app_version, get_db, get_settings, require_api_token
from mobile.factory_page import render_factory_page
from mobile.schemas import HardwareCheckRequest, InstallApplyRequest
from product.demo_mode import build_demo_mode, demo_mode_to_dict
from product.factory_report import build_factory_report, factory_report_to_dict
from product.fleet_snapshot import build_fleet_snapshot, fleet_snapshot_to_dict
from product.hardware_validation import (
    HardwareValidationService,
    hardware_validation_summary_to_dict,
)
from product.install_plan import build_install_plan, install_plan_to_dict
from product.install_runner import execute_install_plan, install_execution_to_dict
from product.observability import build_observability_snapshot, observability_snapshot_to_dict
from product.pilot_plan import build_pilot_plan, pilot_plan_to_dict
from product.provisioning_plan import build_provisioning_plan, provisioning_plan_to_dict
from product.security_audit import build_security_audit, security_audit_to_dict
from product.support_bundle import build_support_bundle, support_bundle_to_dict

router = APIRouter(tags=["factory"])

auth_dep = Depends(require_api_token)
db_dep = Depends(get_db)


@router.get("/factory", response_class=HTMLResponse, summary="Página de fábrica (pública)")
async def factory_page() -> str:
    return render_factory_page()


@router.get("/factory/report", summary="Reporte de preparación de la unidad")
async def factory_report(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return factory_report_to_dict(
        build_factory_report(db, get_settings(request), app_version=get_app_version(request))
    )


@router.get("/factory/provisioning-plan", summary="Plan de aprovisionamiento")
async def factory_provisioning_plan(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return provisioning_plan_to_dict(build_provisioning_plan(db, get_settings(request)))


@router.get("/factory/install-plan", summary="Plan de instalación (dry-run)")
async def factory_install_plan(
    request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return install_plan_to_dict(build_install_plan(get_settings(request)))


@router.post("/factory/install-plan/apply", summary="Ejecutar plan de instalación (gated)")
async def factory_install_plan_apply(
    request: InstallApplyRequest,
    http_request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return install_execution_to_dict(
        execute_install_plan(get_settings(http_request), apply=request.apply, step=request.step)
    )


@router.get("/fleet/snapshot", summary="Snapshot de estado para flota")
async def fleet_snapshot(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return fleet_snapshot_to_dict(
        build_fleet_snapshot(db, get_settings(request), app_version=get_app_version(request))
    )


@router.get("/support/bundle", summary="Bundle de soporte sanitizado")
async def support_bundle(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return support_bundle_to_dict(
        build_support_bundle(db, get_settings(request), app_version=get_app_version(request))
    )


@router.get("/observability", summary="Métricas operacionales locales")
async def observability(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return observability_snapshot_to_dict(build_observability_snapshot(db, get_settings(request)))


@router.get("/demo-mode", summary="Guion de demo")
async def demo_mode(
    _: None = auth_dep,
) -> dict[str, Any]:
    return demo_mode_to_dict(build_demo_mode())


@router.get("/pilot/plan", summary="Plan del piloto")
async def pilot_plan(
    _: None = auth_dep,
) -> dict[str, Any]:
    return pilot_plan_to_dict(build_pilot_plan())


@router.get("/security/audit", summary="Auditoría de seguridad de la unidad")
async def security_audit(
    request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return security_audit_to_dict(build_security_audit(get_settings(request)))


@router.get("/hardware/checks", summary="Estado de chequeos de hardware")
async def hardware_checks(
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return hardware_validation_summary_to_dict(HardwareValidationService(db).summary())


@router.post("/hardware/checks", summary="Registrar resultado de chequeo de hardware")
async def record_hardware_check(
    request: HardwareCheckRequest,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    summary = HardwareValidationService(db).record(
        name=request.name,
        status=request.status,
        detail=request.detail,
    )
    return hardware_validation_summary_to_dict(summary)
