"""Rutas de setup/primer arranque: página, flujo, WiFi, hotspot, QR."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response

from db.database import Database
from mobile.deps import get_db, get_settings, require_api_token
from mobile.schemas import (
    FirstRunSetupRequest,
    HotspotActionRequest,
    WiFiSetupRequest,
    first_run_payload,
)
from mobile.setup_page import render_setup_page
from product.first_run import apply_first_run_setup, first_run_result_to_dict
from product.hotspot_setup import (
    HotspotSetupService,
    build_hotspot_plan,
    hotspot_action_result_to_dict,
    hotspot_plan_to_dict,
)
from product.setup_flow import build_setup_flow, setup_flow_to_dict
from product.setup_qr import (
    build_setup_qr_payload,
    render_setup_card_svg,
    setup_qr_payload_to_dict,
)
from product.wifi_setup import WiFiSetupService, wifi_setup_result_to_dict

router = APIRouter(tags=["setup"])

auth_dep = Depends(require_api_token)
db_dep = Depends(get_db)


@router.get("/setup", response_class=HTMLResponse, summary="Página de setup (pública)")
async def setup_page() -> str:
    return render_setup_page()


@router.get("/setup/flow", summary="Próximo paso del primer arranque")
async def setup_flow(
    request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    return setup_flow_to_dict(build_setup_flow(db, get_settings(request)))


@router.post("/setup/wifi", summary="Registrar/aplicar WiFi (sin persistir password)")
async def setup_wifi(
    request: WiFiSetupRequest,
    http_request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    settings = get_settings(http_request)
    service = WiFiSetupService(db, apply_enabled=settings.rako_wifi_apply_enabled)
    try:
        result = service.configure(
            ssid=request.ssid,
            password=request.password,
            apply=request.apply,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return wifi_setup_result_to_dict(result)


@router.get("/setup/hotspot/plan", summary="Plan del hotspot de emparejamiento")
async def setup_hotspot_plan(
    request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return hotspot_plan_to_dict(build_hotspot_plan(get_settings(request)))


@router.post("/setup/hotspot/start", summary="Levantar hotspot (gated)")
async def setup_hotspot_start(
    request: HotspotActionRequest,
    http_request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return hotspot_action_result_to_dict(
        HotspotSetupService(get_settings(http_request)).start(
            password=request.password, apply=request.apply
        )
    )


@router.post("/setup/hotspot/stop", summary="Bajar hotspot (gated)")
async def setup_hotspot_stop(
    request: HotspotActionRequest,
    http_request: Request,
    _: None = auth_dep,
) -> dict[str, Any]:
    return hotspot_action_result_to_dict(
        HotspotSetupService(get_settings(http_request)).stop(apply=request.apply)
    )


@router.get("/setup/qr", summary="Payload de la tarjeta de setup")
async def setup_qr(
    request: Request,
    serial: str | None = Query(default=None, max_length=80),
    lot: str | None = Query(default=None, max_length=80),
    _: None = auth_dep,
) -> dict[str, Any]:
    return setup_qr_payload_to_dict(
        build_setup_qr_payload(get_settings(request), serial=serial, lot=lot)
    )


@router.get("/setup/qr.svg", summary="Tarjeta de setup imprimible (SVG)")
async def setup_qr_svg(
    request: Request,
    serial: str | None = Query(default=None, max_length=80),
    lot: str | None = Query(default=None, max_length=80),
    _: None = auth_dep,
) -> Response:
    payload = build_setup_qr_payload(get_settings(request), serial=serial, lot=lot)
    return Response(content=render_setup_card_svg(payload), media_type="image/svg+xml")


@router.post("/setup/first-run", summary="Configuración completa en una llamada")
async def setup_first_run(
    request: FirstRunSetupRequest,
    http_request: Request,
    _: None = auth_dep,
    db: Database = db_dep,
) -> dict[str, Any]:
    try:
        result = apply_first_run_setup(db, get_settings(http_request), first_run_payload(request))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return first_run_result_to_dict(result)
