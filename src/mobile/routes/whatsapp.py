"""Rutas del canal WhatsApp: envíos internos + webhook de Meta."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from channels.whatsapp.service import (
    WhatsAppService,
    inbound_result_to_dict,
    outbound_message_to_dict,
)
from channels.whatsapp.webhook import (
    extract_text_messages,
    verify_meta_signature,
    verify_webhook_challenge,
)
from db.database import Database
from mobile.deps import (
    build_whatsapp_client,
    db_dep,
    get_settings,
    get_whatsapp_service,
    require_api_token,
)
from mobile.schemas import (
    WhatsAppCheckinRequest,
    WhatsAppInboundRequest,
    WhatsAppProgressRequest,
)
from product.whatsapp_templates import whatsapp_templates_to_dict

router = APIRouter(tags=["whatsapp"])

auth_dep = Depends(require_api_token)
whatsapp_dep = Depends(get_whatsapp_service)


@router.post("/whatsapp/checkin", summary="Enviar check-in")
async def whatsapp_checkin(
    request: WhatsAppCheckinRequest,
    _: None = auth_dep,
    service: WhatsAppService = whatsapp_dep,
) -> dict[str, Any]:
    return outbound_message_to_dict(service.send_checkin(to=request.to))


@router.post("/whatsapp/progress", summary="Enviar reporte de progreso")
async def whatsapp_progress(
    request: WhatsAppProgressRequest,
    _: None = auth_dep,
    service: WhatsAppService = whatsapp_dep,
) -> dict[str, Any]:
    return outbound_message_to_dict(
        service.send_progress_report(to=request.to, period=request.period)
    )


@router.post("/whatsapp/actions", summary="Enviar menú de acciones")
async def whatsapp_actions(
    request: WhatsAppCheckinRequest,
    _: None = auth_dep,
    service: WhatsAppService = whatsapp_dep,
) -> dict[str, Any]:
    return outbound_message_to_dict(service.send_action_menu(to=request.to))


@router.get("/whatsapp/templates", summary="Plantillas Meta del canal")
async def whatsapp_templates(
    _: None = auth_dep,
) -> dict[str, Any]:
    return whatsapp_templates_to_dict()


@router.post("/whatsapp/inbound", summary="Simular mensaje entrante (interno)")
async def whatsapp_inbound(
    request: WhatsAppInboundRequest,
    _: None = auth_dep,
    service: WhatsAppService = whatsapp_dep,
) -> dict[str, Any]:
    return inbound_result_to_dict(
        service.handle_inbound(from_number=request.from_number, text=request.text)
    )


@router.get("/whatsapp/webhook", response_class=PlainTextResponse, summary="Verificación de Meta")
async def whatsapp_webhook_verify(
    request: Request,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    challenge = verify_webhook_challenge(
        mode=hub_mode,
        verify_token=hub_verify_token,
        challenge=hub_challenge,
        expected_verify_token=get_settings(request).whatsapp_cloud_verify_token,
    )
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid token")
    return challenge


@router.post("/whatsapp/webhook", summary="Webhook de mensajes de Meta")
async def whatsapp_webhook_receive(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    db: Database = db_dep,
) -> dict[str, Any]:
    settings = get_settings(request)
    body = await request.body()
    if settings.rako_env != "dev" and not settings.whatsapp_cloud_app_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WHATSAPP_CLOUD_APP_SECRET is required outside dev",
        )
    if not verify_meta_signature(
        body=body,
        signature_header=x_hub_signature_256,
        app_secret=settings.whatsapp_cloud_app_secret,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid signature")
    payload = await request.json()
    if not isinstance(payload, dict):
        return {"processed": 0}
    messages = extract_text_messages(payload)
    service = WhatsAppService(db, build_whatsapp_client(settings))
    results = [
        inbound_result_to_dict(
            service.handle_inbound(from_number=message.from_number, text=message.text)
        )
        for message in messages
    ]
    return {"processed": len(results), "results": results}
