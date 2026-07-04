"""Modelos de request de la API móvil (validación en el borde).

Separados de la app FastAPI para que los routers por dominio los
compartan sin imports circulares.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from product.first_run import FirstRunMemory, FirstRunPayload


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


class FirstRunMemoryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=240)
    category: Literal["study", "routine", "motivation", "preference", "boundary"] = "preference"
    sensitivity: Literal["normal", "sensitive"] = "normal"


class FirstRunSetupRequest(BaseModel):
    profile: UserProfileRequest = Field(default_factory=UserProfileRequest)
    consent: PrivacyConsentRequest = Field(default_factory=PrivacyConsentRequest)
    channels: ChannelConfigRequest = Field(default_factory=ChannelConfigRequest)
    memories: list[FirstRunMemoryRequest] = Field(default_factory=list, max_length=20)
    wifi_password: str | None = Field(default=None, max_length=128)
    apply_wifi: bool = False
    serial: str | None = Field(default=None, max_length=80)
    lot: str | None = Field(default=None, max_length=80)
    assigned_user_label: str | None = Field(default=None, max_length=120)


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


class InstallApplyRequest(BaseModel):
    apply: bool = False
    step: str | None = Field(default=None, max_length=80)


def first_run_payload(request: FirstRunSetupRequest) -> FirstRunPayload:
    return FirstRunPayload(
        profile=request.profile.model_dump(exclude_none=True),
        consent=request.consent.model_dump(exclude_none=True),
        channels=request.channels.model_dump(exclude_none=True),
        memories=tuple(
            FirstRunMemory(
                text=memory.text,
                category=memory.category,
                sensitivity=memory.sensitivity,
            )
            for memory in request.memories
        ),
        wifi_password=request.wifi_password,
        apply_wifi=request.apply_wifi,
        serial=request.serial,
        lot=request.lot,
        assigned_user_label=request.assigned_user_label,
    )
