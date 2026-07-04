"""Rutas núcleo: salud, pairing, estado, tareas, progreso, foco."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from mobile.deps import get_mobile_service, get_settings, require_api_token
from mobile.schemas import StartFocusRequest
from mobile.service import MobileService, focus_start_to_dict, status_to_dict, task_list_to_dict
from productivity.progress import build_progress_summary, progress_summary_to_dict
from productivity.study_plan import build_study_plan, study_plan_to_dict

router = APIRouter(tags=["core"])

auth_dep = Depends(require_api_token)
service_dep = Depends(get_mobile_service)


@router.get("/health", summary="Liveness check (público)")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/pairing/info", summary="Info pública para emparejar la app")
async def pairing_info(request: Request) -> dict[str, Any]:
    """Lo mínimo que la app Flutter necesita para conectarse — sin secretos.

    El token NUNCA sale por aquí: llega a la app vía la tarjeta QR de setup
    (`/setup/qr.svg`) o lo digita el usuario.
    """
    settings = get_settings(request)
    return {
        "name": "Rako",
        "app_version": request.app.state.app_version,
        "requires_token": bool(settings.rako_api_token) or settings.rako_env != "dev",
        "docs_url": "/docs",
    }


@router.get("/status", summary="Estado general del dispositivo")
async def get_status(
    _: None = auth_dep,
    service: MobileService = service_dep,
) -> dict[str, Any]:
    return status_to_dict(service.status())


@router.get("/tasks", summary="Lista de tareas")
async def tasks(
    limit: int = Query(default=20, ge=1, le=100),
    pending_only: bool = False,
    _: None = auth_dep,
    service: MobileService = service_dep,
) -> dict[str, Any]:
    return task_list_to_dict(service.tasks(limit=limit, pending_only=pending_only))


@router.get("/progress/today", summary="Progreso de hoy")
async def progress_today(
    _: None = auth_dep,
    service: MobileService = service_dep,
) -> dict[str, Any]:
    return progress_summary_to_dict(build_progress_summary(service.db, period="today"))


@router.get("/progress/week", summary="Progreso de la semana")
async def progress_week(
    _: None = auth_dep,
    service: MobileService = service_dep,
) -> dict[str, Any]:
    return progress_summary_to_dict(build_progress_summary(service.db, period="week"))


@router.get("/coach/plan", summary="Plan de estudio sugerido")
async def coach_plan(
    _: None = auth_dep,
    service: MobileService = service_dep,
) -> dict[str, Any]:
    return study_plan_to_dict(build_study_plan(service.db))


@router.post("/focus/start", summary="Iniciar sesión de foco")
async def start_focus(
    request: StartFocusRequest,
    _: None = auth_dep,
    service: MobileService = service_dep,
) -> dict[str, Any]:
    return focus_start_to_dict(service.start_focus(title=request.title, minutes=request.minutes))


@router.post("/focus/cancel", summary="Cancelar sesión de foco")
async def cancel_focus(
    _: None = auth_dep,
    service: MobileService = service_dep,
) -> dict[str, bool]:
    return {"cancelled": service.cancel_focus()}
