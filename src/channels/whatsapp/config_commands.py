"""Comandos de configuración por WhatsApp: pausa, estado, export y borrado."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from channels.whatsapp.pending_flows import pending_expires_at
from channels.whatsapp.results import WhatsAppInboundResult
from product.user_config import UserConfigService

if TYPE_CHECKING:
    from channels.whatsapp.service import WhatsAppService

_PAUSE_TRIGGERS = frozenset(
    {"pausar mensajes", "pausa mensajes", "no me escribas", "silenciar rako", "silenciar"}
)
_RESUME_TRIGGERS = frozenset(
    {"reanudar mensajes", "activar mensajes", "volver a escribirme", "reactivar rako"}
)
_STATUS_TRIGGERS = frozenset({"configuración", "configuracion", "ajustes", "mi configuración"})
_EXPORT_TRIGGERS = frozenset({"exportar mis datos", "mis datos", "datos"})
_DELETE_TRIGGERS = frozenset({"borrar mis datos", "eliminar mis datos"})


def handle_config_command(
    service: WhatsAppService, text: str, *, from_number: str, now: datetime
) -> WhatsAppInboundResult | None:
    normalized = text.lower().strip()
    config = UserConfigService(service._db)
    if normalized in _PAUSE_TRIGGERS:
        return _pause_messages(service, config, from_number=from_number)
    if normalized in _RESUME_TRIGGERS:
        return _resume_messages(service, config, from_number=from_number)
    if normalized in _STATUS_TRIGGERS:
        return service._reply(
            to=from_number,
            action="CONFIG_STATUS",
            response_text=config_status_message(config),
        )
    if normalized in _EXPORT_TRIGGERS:
        return service._reply(
            to=from_number,
            action="USER_DATA_EXPORT",
            response_text=compact_user_data_message(config.export_user_data()),
        )
    if normalized in _DELETE_TRIGGERS:
        return _request_delete_confirmation(service, from_number=from_number, now=now)
    return None


def _pause_messages(
    service: WhatsAppService, config: UserConfigService, *, from_number: str
) -> WhatsAppInboundResult:
    config.update_consent({"proactive_messages_enabled": False})
    return service._reply(
        to=from_number,
        action="MESSAGES_PAUSED",
        response_text=(
            "Listo, pausé los mensajes proactivos. "
            "Puedes escribirme igual cuando quieras. Para volver: reanudar mensajes."
        ),
    )


def _resume_messages(
    service: WhatsAppService, config: UserConfigService, *, from_number: str
) -> WhatsAppInboundResult:
    if not config.whatsapp_can_send():
        return service._reply(
            to=from_number,
            action="CONSENT_REQUIRED",
            response_text=(
                "Antes necesito que WhatsApp esté activado en la configuración de Rako."
            ),
        )
    config.update_consent({"proactive_messages_enabled": True})
    return service._reply(
        to=from_number,
        action="MESSAGES_RESUMED",
        response_text="Listo, reanudé los mensajes proactivos de estudio.",
    )


def _request_delete_confirmation(
    service: WhatsAppService, *, from_number: str, now: datetime
) -> WhatsAppInboundResult:
    service._store_pending(
        from_number,
        {"action": "delete_user_data", "expires_at": pending_expires_at(now)},
    )
    return service._reply(
        to=from_number,
        action="DELETE_USER_DATA_CONFIRM",
        response_text=(
            "Esto borra TODO tu historial en este dispositivo: perfil, "
            "consentimiento, canales, memoria editable, tareas, "
            "interacciones, estados de ánimo y logros. Es permanente. "
            "Para confirmar, responde: confirmar borrar mis datos."
        ),
    )


def config_status_message(config: UserConfigService) -> str:
    consent = config.get_consent()
    channels = config.get_channels()
    return (
        "Configuración actual:\n"
        f"- WhatsApp: {yes_no(consent.whatsapp_enabled and bool(channels.whatsapp_number))}\n"
        f"- Mensajes proactivos: {yes_no(config.proactive_messages_can_send())}\n"
        f"- Reportes de progreso: {yes_no(config.progress_reports_can_send())}\n"
        f"- Memorias guardadas: {len(config.list_memory())}\n"
        "Comandos útiles: pausar mensajes, reanudar mensajes, exportar mis datos, borrar mis datos."
    )


def compact_user_data_message(export: dict[str, object]) -> str:
    profile = export.get("profile")
    consent = export.get("consent")
    channels = export.get("channels")
    memory = export.get("memory")
    preferred_name = profile.get("preferred_name") if isinstance(profile, dict) else None
    university = profile.get("university") if isinstance(profile, dict) else None
    whatsapp_enabled = consent.get("whatsapp_enabled") if isinstance(consent, dict) else False
    wifi_ssid = channels.get("wifi_ssid") if isinstance(channels, dict) else None
    memory_count = len(memory) if isinstance(memory, list) else 0
    return (
        "Resumen de tus datos locales:\n"
        f"- Nombre: {preferred_name or 'sin configurar'}\n"
        f"- Universidad: {university or 'sin configurar'}\n"
        f"- WiFi guardado: {wifi_ssid or 'sin configurar'}\n"
        f"- WhatsApp activo: {yes_no(bool(whatsapp_enabled))}\n"
        f"- Memorias: {memory_count}\n"
        "Desde la API local puedes exportar el detalle completo en /user/export."
    )


def yes_no(value: bool) -> str:
    return "sí" if value else "no"
