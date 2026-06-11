"""FastAPI adapter for the Rako mobile app.

Run locally on the Pi:

    PYTHONPATH=src uvicorn mobile.api:create_app --factory --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from channels.whatsapp.client import InMemoryWhatsAppClient
from channels.whatsapp.service import (
    WhatsAppService,
    inbound_result_to_dict,
    outbound_message_to_dict,
)
from config import Settings
from db.database import Database
from mobile.service import MobileService, focus_start_to_dict, status_to_dict, task_list_to_dict
from productivity.progress import build_progress_summary, progress_summary_to_dict


class StartFocusRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    minutes: int = Field(default=25, ge=1, le=180)


class WhatsAppCheckinRequest(BaseModel):
    to: str = Field(min_length=3, max_length=32)


class WhatsAppProgressRequest(BaseModel):
    to: str = Field(min_length=3, max_length=32)
    period: Literal["today", "week"] = "today"


class WhatsAppInboundRequest(BaseModel):
    from_number: str = Field(min_length=3, max_length=32)
    text: str = Field(min_length=0, max_length=1000)


def create_app() -> Any:
    try:
        from fastapi import (
            Depends,
            FastAPI,
            Header,
            HTTPException,
            Query,
            status,
        )
    except ImportError as exc:  # pragma: no cover - depends on optional HTTP deps
        raise RuntimeError("Install fastapi and uvicorn to run the mobile API") from exc

    settings = Settings()
    app = FastAPI(title="Rako Local API", version="0.1.0")

    async def require_api_token(
        authorization: str | None = Header(default=None),
    ) -> None:
        token = settings.rako_api_token
        if not token:
            if settings.rako_env == "dev":
                return
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="RAKO_API_TOKEN is required outside dev",
            )
        expected = f"Bearer {token}"
        if authorization != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing or invalid API token",
            )

    async def build_service() -> AsyncIterator[MobileService]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            yield MobileService(db)
        finally:
            db.close()

    async def build_whatsapp_service() -> AsyncIterator[WhatsAppService]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            yield WhatsAppService(db, InMemoryWhatsAppClient())
        finally:
            db.close()

    auth_dep = Depends(require_api_token)
    service_dep = Depends(build_service)
    whatsapp_dep = Depends(build_whatsapp_service)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    async def get_status(
        _: None = auth_dep,
        service: MobileService = service_dep,
    ) -> dict[str, Any]:
        return status_to_dict(service.status())

    @app.get("/tasks")
    async def tasks(
        limit: int = Query(default=20, ge=1, le=100),
        pending_only: bool = False,
        _: None = auth_dep,
        service: MobileService = service_dep,
    ) -> dict[str, Any]:
        return task_list_to_dict(service.tasks(limit=limit, pending_only=pending_only))

    @app.get("/progress/today")
    async def progress_today(
        _: None = auth_dep,
        service: MobileService = service_dep,
    ) -> dict[str, Any]:
        return progress_summary_to_dict(build_progress_summary(service.db, period="today"))

    @app.get("/progress/week")
    async def progress_week(
        _: None = auth_dep,
        service: MobileService = service_dep,
    ) -> dict[str, Any]:
        return progress_summary_to_dict(build_progress_summary(service.db, period="week"))

    @app.post("/focus/start")
    async def start_focus(
        request: StartFocusRequest,
        _: None = auth_dep,
        service: MobileService = service_dep,
    ) -> dict[str, Any]:
        return focus_start_to_dict(
            service.start_focus(title=request.title, minutes=request.minutes)
        )

    @app.post("/focus/cancel")
    async def cancel_focus(
        _: None = auth_dep,
        service: MobileService = service_dep,
    ) -> dict[str, bool]:
        return {"cancelled": service.cancel_focus()}

    @app.post("/whatsapp/checkin")
    async def whatsapp_checkin(
        request: WhatsAppCheckinRequest,
        _: None = auth_dep,
        service: WhatsAppService = whatsapp_dep,
    ) -> dict[str, Any]:
        return outbound_message_to_dict(service.send_checkin(to=request.to))

    @app.post("/whatsapp/progress")
    async def whatsapp_progress(
        request: WhatsAppProgressRequest,
        _: None = auth_dep,
        service: WhatsAppService = whatsapp_dep,
    ) -> dict[str, Any]:
        return outbound_message_to_dict(
            service.send_progress_report(to=request.to, period=request.period)
        )

    @app.post("/whatsapp/actions")
    async def whatsapp_actions(
        request: WhatsAppCheckinRequest,
        _: None = auth_dep,
        service: WhatsAppService = whatsapp_dep,
    ) -> dict[str, Any]:
        return outbound_message_to_dict(service.send_action_menu(to=request.to))

    @app.post("/whatsapp/inbound")
    async def whatsapp_inbound(
        request: WhatsAppInboundRequest,
        _: None = auth_dep,
        service: WhatsAppService = whatsapp_dep,
    ) -> dict[str, Any]:
        return inbound_result_to_dict(
            service.handle_inbound(from_number=request.from_number, text=request.text)
        )

    return app
