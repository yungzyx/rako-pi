"""Rutas de usuario: perfil, consentimiento, canales, memoria, datos."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from mobile.deps import get_user_config_service, require_api_token
from mobile.schemas import (
    ChannelConfigRequest,
    MemoryCreateRequest,
    PrivacyConsentRequest,
    UserProfileRequest,
)
from product.user_config import (
    UserConfigService,
    channels_to_dict,
    consent_to_dict,
    memory_to_dict,
    onboarding_status_to_dict,
    user_profile_to_dict,
)

router = APIRouter(tags=["user"])

auth_dep = Depends(require_api_token)
user_config_dep = Depends(get_user_config_service)


@router.get("/onboarding/status", summary="Qué falta para que el dispositivo esté listo")
async def onboarding_status(
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return onboarding_status_to_dict(service.onboarding_status())


@router.get("/user/profile", summary="Perfil del usuario")
async def get_user_profile(
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return user_profile_to_dict(service.get_profile())


@router.patch("/user/profile", summary="Actualizar perfil")
async def update_user_profile(
    request: UserProfileRequest,
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return user_profile_to_dict(service.update_profile(request.model_dump(exclude_none=True)))


@router.get("/user/consent", summary="Consentimientos de privacidad")
async def get_privacy_consent(
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return consent_to_dict(service.get_consent())


@router.patch("/user/consent", summary="Actualizar consentimientos")
async def update_privacy_consent(
    request: PrivacyConsentRequest,
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return consent_to_dict(service.update_consent(request.model_dump(exclude_none=True)))


@router.get("/user/channels", summary="Canales configurados (WhatsApp, contactos)")
async def get_channel_config(
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return channels_to_dict(service.get_channels())


@router.patch("/user/channels", summary="Actualizar canales")
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


@router.get("/user/memory", summary="Memoria editable del usuario")
async def list_user_memory(
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return {"items": [memory_to_dict(item) for item in service.list_memory()]}


@router.post("/user/memory", summary="Agregar recuerdo editable")
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


@router.delete("/user/memory/{memory_id}", summary="Borrar un recuerdo")
async def delete_user_memory(
    memory_id: str,
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, bool]:
    return {"deleted": service.delete_memory(memory_id)}


@router.get("/user/export", summary="Exportar datos del usuario")
async def export_user_data(
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    return service.export_user_data()


@router.post("/user/delete-all", summary="Borrado total (irreversible)")
async def delete_user_data(
    _: None = auth_dep,
    service: UserConfigService = user_config_dep,
) -> dict[str, Any]:
    deleted = service.delete_user_data()
    return {
        "deleted": deleted,
        "deleted_count": sum(1 for was_deleted in deleted.values() if was_deleted),
    }
