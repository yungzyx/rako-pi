"""FastAPI adapter for the Rako mobile app.

Run locally on the Pi:

    PYTHONPATH=src uvicorn mobile.api:create_app --factory --host 127.0.0.1 --port 8765
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
from product.setup_flow import build_setup_flow, setup_flow_to_dict
from product.user_config import (
    UserConfigService,
    channels_to_dict,
    consent_to_dict,
    memory_to_dict,
    onboarding_status_to_dict,
    user_profile_to_dict,
)
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


class UserProfileRequest(BaseModel):
    preferred_name: str | None = Field(default=None, max_length=80)
    university: str | None = Field(default=None, max_length=120)
    program: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, max_length=16)


class PrivacyConsentRequest(BaseModel):
    whatsapp_enabled: bool | None = None
    proactive_messages_enabled: bool | None = None
    progress_reports_enabled: bool | None = None
    sensitive_memory_enabled: bool | None = None
    wellbeing_escalation_enabled: bool | None = None


class ChannelConfigRequest(BaseModel):
    whatsapp_number: str | None = Field(default=None, max_length=32)
    trusted_contact_name: str | None = Field(default=None, max_length=120)
    trusted_contact_phone: str | None = Field(default=None, max_length=32)
    wellbeing_unit_name: str | None = Field(default=None, max_length=160)
    wellbeing_unit_phone: str | None = Field(default=None, max_length=32)
    wifi_ssid: str | None = Field(default=None, max_length=64)


class MemoryCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=240)
    category: Literal["study", "routine", "motivation", "preference", "boundary"] = "preference"
    sensitivity: Literal["normal", "sensitive"] = "normal"


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

    async def build_user_config_service() -> AsyncIterator[UserConfigService]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            yield UserConfigService(db)
        finally:
            db.close()

    auth_dep = Depends(require_api_token)
    service_dep = Depends(build_service)
    whatsapp_dep = Depends(build_whatsapp_service)
    user_config_dep = Depends(build_user_config_service)

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

    @app.get("/onboarding/status")
    async def onboarding_status(
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return onboarding_status_to_dict(service.onboarding_status())

    @app.get("/setup/flow")
    async def setup_flow(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return setup_flow_to_dict(build_setup_flow(db, settings))
        finally:
            db.close()

    @app.get("/user/profile")
    async def get_user_profile(
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return user_profile_to_dict(service.get_profile())

    @app.patch("/user/profile")
    async def update_user_profile(
        request: UserProfileRequest,
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return user_profile_to_dict(service.update_profile(request.model_dump(exclude_none=True)))

    @app.get("/user/consent")
    async def get_privacy_consent(
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return consent_to_dict(service.get_consent())

    @app.patch("/user/consent")
    async def update_privacy_consent(
        request: PrivacyConsentRequest,
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return consent_to_dict(service.update_consent(request.model_dump(exclude_none=True)))

    @app.get("/user/channels")
    async def get_channel_config(
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return channels_to_dict(service.get_channels())

    @app.patch("/user/channels")
    async def update_channel_config(
        request: ChannelConfigRequest,
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        try:
            channels = service.update_channels(request.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return channels_to_dict(channels)

    @app.get("/user/memory")
    async def list_user_memory(
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return {"items": [memory_to_dict(item) for item in service.list_memory()]}

    @app.post("/user/memory")
    async def add_user_memory(
        request: MemoryCreateRequest,
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        try:
            memory = service.add_memory(
                text=request.text,
                category=request.category,
                sensitivity=request.sensitivity,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return memory_to_dict(memory)

    @app.delete("/user/memory/{memory_id}")
    async def delete_user_memory(
        memory_id: str,
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, bool]:
        return {"deleted": service.delete_memory(memory_id)}

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
