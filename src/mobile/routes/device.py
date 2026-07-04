"""Rutas de dispositivo: identidad, heartbeat, reasignación, OTA."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from db.database import Database
from mobile.deps import get_app_version, get_db, get_settings, require_api_token
from mobile.schemas import DeviceHeartbeatRequest, DeviceProvisionRequest, UpdateApplyRequest
from product.device_registry import (
    DeviceRegistryService,
    device_heartbeat_to_dict,
    device_identity_to_dict,
    reassignment_reset_to_dict,
)
from product.update_status import (
    apply_update,
    build_update_plan,
    build_update_status,
    update_apply_result_to_dict,
    update_plan_to_dict,
    update_status_to_dict,
)

router = APIRouter(tags=["device"])

auth_dep = Depends(require_api_token)
db_dep = Depends(get_db)


@router.get("/device/identity", summary="Identidad del dispositivo")
async def device_identity(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return device_identity_to_dict(DeviceRegistryService(db, get_settings(request)).get_identity())


@router.patch("/device/identity", summary="Aprovisionar identidad")
async def update_device_identity(
    request: DeviceProvisionRequest,
    http_request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    identity = DeviceRegistryService(db, get_settings(http_request)).provision(
        serial=request.serial,
        lot=request.lot,
        assigned_user_label=request.assigned_user_label,
    )
    return device_identity_to_dict(identity)


@router.post("/device/heartbeat", summary="Registrar heartbeat")
async def device_heartbeat(
    request: DeviceHeartbeatRequest,
    http_request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    heartbeat = DeviceRegistryService(db, get_settings(http_request)).heartbeat(
        app_version=get_app_version(http_request),
        status=request.status,
        detail=request.detail,
    )
    payload = device_heartbeat_to_dict(heartbeat)
    assert payload is not None
    return payload


@router.post("/device/reset-user", summary="Reset para reasignar la unidad")
async def reset_device_user(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return reassignment_reset_to_dict(
        DeviceRegistryService(db, get_settings(request)).reset_for_reassignment()
    )


@router.get("/update/status", summary="Estado de actualización OTA")
async def update_status(
    request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return update_status_to_dict(build_update_status(get_settings(request)))


@router.get("/update/plan", summary="Plan de actualización OTA")
async def update_plan(
    request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return update_plan_to_dict(build_update_plan(get_settings(request)))


@router.post("/update/apply", summary="Aplicar actualización (gated)")
async def update_apply(
    request: UpdateApplyRequest,
    http_request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return update_apply_result_to_dict(
        apply_update(
            get_settings(http_request), artifact_path=request.artifact_path, apply=request.apply
        )
    )
