"""FastAPI adapter for the Rako mobile app.

Run locally on the Pi:

    PYTHONPATH=src uvicorn mobile.api:create_app --factory --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field
from starlette.requests import Request

from channels.whatsapp.client import InMemoryWhatsAppClient, WhatsAppClient, WhatsAppCloudClient
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
from config import Settings
from db.database import Database
from mobile.factory_page import render_factory_page
from mobile.service import MobileService, focus_start_to_dict, status_to_dict, task_list_to_dict
from mobile.setup_page import render_setup_page
from product.device_registry import (
    DeviceRegistryService,
    device_heartbeat_to_dict,
    device_identity_to_dict,
    reassignment_reset_to_dict,
)
from product.factory_report import build_factory_report, factory_report_to_dict
from product.fleet_snapshot import build_fleet_snapshot, fleet_snapshot_to_dict
from product.hardware_validation import (
    HardwareValidationService,
    hardware_validation_summary_to_dict,
)
from product.hotspot_setup import (
    HotspotSetupService,
    build_hotspot_plan,
    hotspot_action_result_to_dict,
    hotspot_plan_to_dict,
)
from product.install_plan import build_install_plan, install_plan_to_dict
from product.provisioning_plan import build_provisioning_plan, provisioning_plan_to_dict
from product.security_audit import build_security_audit, security_audit_to_dict
from product.setup_flow import build_setup_flow, setup_flow_to_dict
from product.setup_qr import (
    build_setup_qr_payload,
    render_setup_card_svg,
    setup_qr_payload_to_dict,
)
from product.support_bundle import build_support_bundle, support_bundle_to_dict
from product.update_status import (
    apply_update,
    build_update_plan,
    build_update_status,
    current_app_version,
    update_apply_result_to_dict,
    update_plan_to_dict,
    update_status_to_dict,
)
from product.user_config import (
    UserConfigService,
    channels_to_dict,
    consent_to_dict,
    memory_to_dict,
    onboarding_status_to_dict,
    user_profile_to_dict,
)
from product.whatsapp_templates import whatsapp_templates_to_dict
from product.wifi_setup import WiFiSetupService, wifi_setup_result_to_dict
from productivity.progress import build_progress_summary, progress_summary_to_dict
from productivity.study_plan import build_study_plan, study_plan_to_dict


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


class WiFiSetupRequest(BaseModel):
    ssid: str = Field(min_length=1, max_length=64)
    password: str | None = Field(default=None, max_length=128)
    apply: bool = False


class HotspotActionRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=64)
    apply: bool = False


class DeviceProvisionRequest(BaseModel):
    serial: str | None = Field(default=None, max_length=80)
    lot: str | None = Field(default=None, max_length=80)
    assigned_user_label: str | None = Field(default=None, max_length=120)


class DeviceHeartbeatRequest(BaseModel):
    status: str = Field(default="ok", max_length=40)
    detail: str | None = Field(default=None, max_length=240)


class HardwareCheckRequest(BaseModel):
    name: Literal["microphone", "speaker", "oled", "button", "focus_flow", "crisis_bypass"]
    status: Literal["pass", "fail"]
    detail: str = Field(default="", max_length=240)


class UpdateApplyRequest(BaseModel):
    artifact_path: str | None = Field(default=None, max_length=500)
    apply: bool = False


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
        from fastapi.responses import HTMLResponse, PlainTextResponse, Response
    except ImportError as exc:  # pragma: no cover - depends on optional HTTP deps
        raise RuntimeError("Install fastapi and uvicorn to run the mobile API") from exc

    settings = Settings()
    app_version = current_app_version()
    app = FastAPI(title="Rako Local API", version=app_version)

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
            yield WhatsAppService(db, _build_whatsapp_client(settings))
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

    @app.get("/setup", response_class=HTMLResponse)
    async def setup_page() -> str:
        return render_setup_page()

    @app.get("/factory", response_class=HTMLResponse)
    async def factory_page() -> str:
        return render_factory_page()

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

    @app.get("/coach/plan")
    async def coach_plan(
        _: None = auth_dep,
        service: MobileService = service_dep,
    ) -> dict[str, Any]:
        return study_plan_to_dict(build_study_plan(service.db))

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

    @app.post("/setup/wifi")
    async def setup_wifi(
        request: WiFiSetupRequest,
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            service = WiFiSetupService(db, apply_enabled=settings.rako_wifi_apply_enabled)
            try:
                result = service.configure(
                    ssid=request.ssid,
                    password=request.password,
                    apply=request.apply,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            return wifi_setup_result_to_dict(result)
        finally:
            db.close()

    @app.get("/setup/hotspot/plan")
    async def setup_hotspot_plan(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return hotspot_plan_to_dict(build_hotspot_plan(settings))

    @app.post("/setup/hotspot/start")
    async def setup_hotspot_start(
        request: HotspotActionRequest,
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return hotspot_action_result_to_dict(
            HotspotSetupService(settings).start(password=request.password, apply=request.apply)
        )

    @app.post("/setup/hotspot/stop")
    async def setup_hotspot_stop(
        request: HotspotActionRequest,
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return hotspot_action_result_to_dict(
            HotspotSetupService(settings).stop(apply=request.apply)
        )

    @app.get("/setup/qr")
    async def setup_qr(
        serial: str | None = Query(default=None, max_length=80),
        lot: str | None = Query(default=None, max_length=80),
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return setup_qr_payload_to_dict(build_setup_qr_payload(settings, serial=serial, lot=lot))

    @app.get("/setup/qr.svg")
    async def setup_qr_svg(
        serial: str | None = Query(default=None, max_length=80),
        lot: str | None = Query(default=None, max_length=80),
        _: None = auth_dep,
    ) -> Response:
        payload = build_setup_qr_payload(settings, serial=serial, lot=lot)
        return Response(content=render_setup_card_svg(payload), media_type="image/svg+xml")

    @app.get("/factory/report")
    async def factory_report(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return factory_report_to_dict(
                build_factory_report(db, settings, app_version=app_version)
            )
        finally:
            db.close()

    @app.get("/factory/provisioning-plan")
    async def factory_provisioning_plan(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return provisioning_plan_to_dict(build_provisioning_plan(db, settings))
        finally:
            db.close()

    @app.get("/factory/install-plan")
    async def factory_install_plan(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return install_plan_to_dict(build_install_plan(settings))

    @app.get("/fleet/snapshot")
    async def fleet_snapshot(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return fleet_snapshot_to_dict(
                build_fleet_snapshot(db, settings, app_version=app_version)
            )
        finally:
            db.close()

    @app.get("/support/bundle")
    async def support_bundle(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return support_bundle_to_dict(
                build_support_bundle(db, settings, app_version=app_version)
            )
        finally:
            db.close()

    @app.get("/security/audit")
    async def security_audit(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return security_audit_to_dict(build_security_audit(settings))

    @app.get("/hardware/checks")
    async def hardware_checks(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return hardware_validation_summary_to_dict(HardwareValidationService(db).summary())
        finally:
            db.close()

    @app.post("/hardware/checks")
    async def record_hardware_check(
        request: HardwareCheckRequest,
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            summary = HardwareValidationService(db).record(
                name=request.name,
                status=request.status,
                detail=request.detail,
            )
            return hardware_validation_summary_to_dict(summary)
        finally:
            db.close()

    @app.get("/device/identity")
    async def device_identity(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return device_identity_to_dict(DeviceRegistryService(db, settings).get_identity())
        finally:
            db.close()

    @app.patch("/device/identity")
    async def update_device_identity(
        request: DeviceProvisionRequest,
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            identity = DeviceRegistryService(db, settings).provision(
                serial=request.serial,
                lot=request.lot,
                assigned_user_label=request.assigned_user_label,
            )
            return device_identity_to_dict(identity)
        finally:
            db.close()

    @app.post("/device/heartbeat")
    async def device_heartbeat(
        request: DeviceHeartbeatRequest,
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            heartbeat = DeviceRegistryService(db, settings).heartbeat(
                app_version=app_version,
                status=request.status,
                detail=request.detail,
            )
            payload = device_heartbeat_to_dict(heartbeat)
            assert payload is not None
            return payload
        finally:
            db.close()

    @app.post("/device/reset-user")
    async def reset_device_user(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            return reassignment_reset_to_dict(
                DeviceRegistryService(db, settings).reset_for_reassignment()
            )
        finally:
            db.close()

    @app.get("/update/status")
    async def update_status(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return update_status_to_dict(build_update_status(settings))

    @app.get("/update/plan")
    async def update_plan(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return update_plan_to_dict(build_update_plan(settings))

    @app.post("/update/apply")
    async def update_apply(
        request: UpdateApplyRequest,
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return update_apply_result_to_dict(
            apply_update(settings, artifact_path=request.artifact_path, apply=request.apply)
        )

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

    @app.get("/user/export")
    async def export_user_data(
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        return service.export_user_data()

    @app.post("/user/delete-all")
    async def delete_user_data(
        _: None = auth_dep,
        service: UserConfigService = user_config_dep,
    ) -> dict[str, Any]:
        deleted = service.delete_user_data()
        return {
            "deleted": deleted,
            "deleted_count": sum(1 for was_deleted in deleted.values() if was_deleted),
        }

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

    @app.get("/whatsapp/templates")
    async def whatsapp_templates(
        _: None = auth_dep,
    ) -> dict[str, Any]:
        return whatsapp_templates_to_dict()

    @app.post("/whatsapp/inbound")
    async def whatsapp_inbound(
        request: WhatsAppInboundRequest,
        _: None = auth_dep,
        service: WhatsAppService = whatsapp_dep,
    ) -> dict[str, Any]:
        return inbound_result_to_dict(
            service.handle_inbound(from_number=request.from_number, text=request.text)
        )

    @app.get("/whatsapp/webhook", response_class=PlainTextResponse)
    async def whatsapp_webhook_verify(
        hub_mode: str | None = Query(default=None, alias="hub.mode"),
        hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ) -> str:
        challenge = verify_webhook_challenge(
            mode=hub_mode,
            verify_token=hub_verify_token,
            challenge=hub_challenge,
            expected_verify_token=settings.whatsapp_cloud_verify_token,
        )
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid token")
        return challenge

    @app.post("/whatsapp/webhook")
    async def whatsapp_webhook_receive(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    ) -> dict[str, Any]:
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
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            service = WhatsAppService(db, _build_whatsapp_client(settings))
            results = [
                inbound_result_to_dict(
                    service.handle_inbound(from_number=message.from_number, text=message.text)
                )
                for message in messages
            ]
            return {"processed": len(results), "results": results}
        finally:
            db.close()

    return app


def _build_whatsapp_client(settings: Settings) -> WhatsAppClient:
    if (
        settings.whatsapp_client == "cloud"
        and settings.whatsapp_cloud_access_token
        and settings.whatsapp_cloud_phone_number_id
    ):
        return WhatsAppCloudClient(
            access_token=settings.whatsapp_cloud_access_token,
            phone_number_id=settings.whatsapp_cloud_phone_number_id,
            api_version=settings.whatsapp_cloud_api_version,
            timeout_s=settings.whatsapp_cloud_timeout_s,
        )
    return InMemoryWhatsAppClient()
