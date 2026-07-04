"""Dependencias compartidas de la API móvil.

Los routers por dominio leen la configuración desde `request.app.state`
(seteada por `create_app`), así los módulos de rutas no cargan `.env`
por su cuenta ni comparten estado global.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status

from channels.whatsapp.client import InMemoryWhatsAppClient, WhatsAppClient, WhatsAppCloudClient
from channels.whatsapp.service import WhatsAppService
from config import Settings
from db.database import Database
from mobile.service import MobileService
from product.user_config import UserConfigService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_app_version(request: Request) -> str:
    return request.app.state.app_version


async def require_api_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    settings = get_settings(request)
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


async def get_db(request: Request) -> AsyncIterator[Database]:
    settings = get_settings(request)
    db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
    try:
        yield db
    finally:
        db.close()


# Singleton a nivel de módulo para usar como default (regla B008: no llamar
# Depends() en defaults de argumentos; los routers reutilizan este objeto).
db_dep = Depends(get_db)


async def get_mobile_service(db: Database = db_dep) -> MobileService:
    return MobileService(db)


async def get_user_config_service(db: Database = db_dep) -> UserConfigService:
    return UserConfigService(db)


async def get_whatsapp_service(request: Request, db: Database = db_dep) -> WhatsAppService:
    return WhatsAppService(db, build_whatsapp_client(get_settings(request)))


def build_whatsapp_client(settings: Settings) -> WhatsAppClient:
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
