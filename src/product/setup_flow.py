"""First-run setup flow for assigning a Rako to one student.

This module translates local configuration into a product-facing checklist that
a setup web page, mobile app, or factory dashboard can render directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from config import Settings
from db.database import Database
from product.factory_acceptance import build_factory_acceptance_checklist
from product.user_config import UserConfigService

SetupStepStatus = Literal["done", "todo", "blocked", "optional", "manual"]


@dataclass(frozen=True, slots=True)
class SetupStep:
    id: str
    title: str
    status: SetupStepStatus
    detail: str
    action: str


@dataclass(frozen=True, slots=True)
class SetupFlow:
    ready_for_user: bool
    completion_percent: int
    next_step_id: str | None
    next_action: str | None
    missing_required: tuple[str, ...]
    warnings: tuple[str, ...]
    privacy_notes: tuple[str, ...]
    steps: tuple[SetupStep, ...]


def build_setup_flow(db: Database, settings: Settings) -> SetupFlow:
    config = UserConfigService(db)
    onboarding = config.onboarding_status()
    profile = onboarding.profile
    consent = onboarding.consent
    channels = onboarding.channels
    factory = build_factory_acceptance_checklist(db, settings)

    steps = (
        _step(
            "profile",
            "Perfil del estudiante",
            "done" if profile.preferred_name else "todo",
            profile.preferred_name or "Falta nombre preferido",
            "Guardar nombre, universidad, carrera y zona horaria.",
        ),
        _step(
            "wifi",
            "WiFi del dispositivo",
            "done" if channels.wifi_ssid else "todo",
            channels.wifi_ssid or "Falta SSID de la red configurada",
            "Conectar Rako a la red del usuario; no guardar la contraseña en SQLite.",
        ),
        _step(
            "privacy",
            "Consentimiento y privacidad",
            "done" if "privacy_consent" not in onboarding.missing else "todo",
            "Consentimiento registrado"
            if "privacy_consent" not in onboarding.missing
            else "Faltan permisos explícitos",
            "Elegir permisos separados para WhatsApp, reportes, memoria y bienestar.",
        ),
        _whatsapp_step(config),
        _step(
            "proactive",
            "Coaching proactivo",
            "done" if config.proactive_messages_can_send() else "optional",
            "Activado" if config.proactive_messages_can_send() else "Desactivado o sin WhatsApp",
            "Permitir mensajes útiles con horario silencioso y opción de pausar.",
        ),
        _wellbeing_step(consent.wellbeing_escalation_enabled, channels.wellbeing_unit_phone),
        _step(
            "memory",
            "Memoria editable",
            "done" if onboarding.memory_count else "optional",
            f"{onboarding.memory_count} recuerdos configurados"
            if onboarding.memory_count
            else "Sin recuerdos iniciales",
            "Agregar preferencias no sensibles, como horarios, estilo de apoyo o bloques favoritos.",
        ),
        _factory_step(factory.automatic_failures, factory.automatic_warnings),
        _step(
            "hardware",
            "Prueba física final",
            "manual",
            "Requiere confirmar micrófono, parlante, ojos, botón, foco y crisis",
            "Ejecutar rako-doctor --full y el checklist humano antes de entregar.",
        ),
    )

    next_step = next((step for step in steps if step.status in {"todo", "blocked"}), None)
    required_steps = tuple(step for step in steps if step.status in {"done", "todo", "blocked"})
    completed_required = sum(1 for step in required_steps if step.status == "done")
    completion_percent = round((completed_required / len(required_steps)) * 100)
    warnings = tuple(
        item.detail
        for item in factory.items
        if item.status == "warn" and item.category in {"whatsapp", "secrets"}
    )
    return SetupFlow(
        ready_for_user=onboarding.ready and factory.automatic_failures == 0,
        completion_percent=completion_percent,
        next_step_id=next_step.id if next_step else None,
        next_action=next_step.action if next_step else None,
        missing_required=tuple(onboarding.missing),
        warnings=warnings,
        privacy_notes=(
            "La contraseña WiFi se usa solo para conectar el sistema, no se guarda en SQLite.",
            "WhatsApp, reportes proactivos, memoria sensible y bienestar tienen permisos separados.",
            "El usuario debe poder ver, editar y borrar la memoria que Rako guarda.",
        ),
        steps=steps,
    )


def setup_flow_to_dict(flow: SetupFlow) -> dict[str, object]:
    return {
        "ready_for_user": flow.ready_for_user,
        "completion_percent": flow.completion_percent,
        "next_step_id": flow.next_step_id,
        "next_action": flow.next_action,
        "missing_required": list(flow.missing_required),
        "warnings": list(flow.warnings),
        "privacy_notes": list(flow.privacy_notes),
        "steps": [asdict(step) for step in flow.steps],
    }


def _whatsapp_step(config: UserConfigService) -> SetupStep:
    consent = config.get_consent()
    channels = config.get_channels()
    if config.whatsapp_can_send():
        status: SetupStepStatus = "done"
        detail = channels.whatsapp_number or "Configurado"
    elif consent.whatsapp_enabled:
        status = "blocked"
        detail = "WhatsApp activado, pero falta número"
    else:
        status = "optional"
        detail = "No activado"
    return _step(
        "whatsapp",
        "WhatsApp del usuario",
        status,
        detail,
        "Vincular número y confirmar consentimiento antes de enviar mensajes.",
    )


def _wellbeing_step(enabled: bool, phone: str | None) -> SetupStep:
    if enabled and phone:
        status: SetupStepStatus = "done"
        detail = phone
    elif enabled:
        status = "blocked"
        detail = "Bienestar activado, pero falta teléfono o destino"
    else:
        status = "optional"
        detail = "No activado"
    return _step(
        "wellbeing",
        "Derivación a bienestar",
        status,
        detail,
        "Configurar unidad/contacto real antes de prometer derivación.",
    )


def _factory_step(failures: int, warnings: int) -> SetupStep:
    if failures:
        status: SetupStepStatus = "blocked"
        detail = f"{failures} bloqueos automáticos"
    else:
        status = "done"
        detail = "Checks automáticos OK" if warnings == 0 else f"OK con {warnings} advertencias"
    return _step(
        "software",
        "Software y credenciales",
        status,
        detail,
        "Resolver tokens, STT/TTS, API local y cifrado antes de entregar.",
    )


def _step(
    id: str,
    title: str,
    status: SetupStepStatus,
    detail: str,
    action: str,
) -> SetupStep:
    return SetupStep(id=id, title=title, status=status, detail=detail, action=action)
