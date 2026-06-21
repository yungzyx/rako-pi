"""WhatsApp Cloud template catalog for production rollout planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

TemplateStatus = Literal["draft", "ready_for_meta", "approved"]


@dataclass(frozen=True, slots=True)
class WhatsAppTemplate:
    name: str
    status: TemplateStatus
    category: str
    language: str
    body: str
    variables: tuple[str, ...]
    safe_outside_24h_window: bool


TEMPLATES: tuple[WhatsAppTemplate, ...] = (
    WhatsAppTemplate(
        name="rako_daily_progress",
        status="ready_for_meta",
        category="utility",
        language="es_CL",
        body="Hoy avanzaste {{1}} bloque(s) de foco. Tu siguiente paso está disponible cuando quieras.",
        variables=("focus_blocks",),
        safe_outside_24h_window=True,
    ),
    WhatsAppTemplate(
        name="rako_gentle_checkin",
        status="ready_for_meta",
        category="utility",
        language="es_CL",
        body="Paso a preguntarte cómo va tu energía para estudiar hoy. Puedes responder con 1, 2 o 3.",
        variables=(),
        safe_outside_24h_window=True,
    ),
    WhatsAppTemplate(
        name="rako_focus_reminder",
        status="ready_for_meta",
        category="utility",
        language="es_CL",
        body="Tienes un bloque corto disponible. Si quieres, partimos con {{1}} minutos.",
        variables=("minutes",),
        safe_outside_24h_window=True,
    ),
)


def list_whatsapp_templates() -> tuple[WhatsAppTemplate, ...]:
    return TEMPLATES


def whatsapp_template_to_dict(template: WhatsAppTemplate) -> dict[str, Any]:
    payload = asdict(template)
    payload["variables"] = list(template.variables)
    return payload


def whatsapp_templates_to_dict() -> dict[str, Any]:
    return {
        "templates": [whatsapp_template_to_dict(template) for template in TEMPLATES],
        "notes": [
            "Submit these templates in Meta before using proactive outbound messages.",
            "Templates avoid task titles, crisis details, raw moods, and sensitive memory.",
        ],
    }
