"""Academic-scope guardrails for Rako.

Rako is an academic companion, not a mental-health assistant. These helpers keep
non-crisis clinical topics out of the LLM path and redirect to UDD resources.
"""

from __future__ import annotations

import re
import unicodedata

from safety.resources import render_crisis_resources, render_soft_udd_resources

_HEALTH_TOPIC_PATTERNS = (
    "angustia",
    "ansiedad",
    "ansioso",
    "ansiosa",
    "ataque de panico",
    "autismo",
    "bipolar",
    "crisis de panico",
    "depresion",
    "deprimido",
    "deprimida",
    "diagnostico",
    "duelo",
    "estres postraumatico",
    "farmaco",
    "medicamento",
    "obsesivo",
    "panico",
    "pastilla",
    "psicologo",
    "psicologa",
    "psiquiatra",
    "salud mental",
    "tdah",
    "terapia",
    "terapeuta",
    "trastorno",
    "trauma",
    "antidepresivo",
    "ansiolitico",
)


def mentions_mental_health_topic(text: str) -> bool:
    normalized = _normalize(text)
    return any(
        re.search(rf"\b{re.escape(pattern)}\b", normalized) for pattern in _HEALTH_TOPIC_PATTERNS
    )


def build_scope_redirect_response() -> str:
    return (
        "Eso supera mi rol. Yo puedo ayudarte con estudio, organización y foco cotidiano. "
        f"{render_soft_udd_resources()}"
    )


def build_elevated_support_response() -> str:
    return (
        "Suena pesado para estudiar ahora. Haz una pausa de 3 respiraciones lentas y elige solo "
        f"el primer paso académico, no todo el problema. {render_soft_udd_resources()}"
    )


def build_wellbeing_referral_response(
    unit_name: str | None = None,
    unit_phone: str | None = None,
) -> str:
    """Derivación cálida a la unidad de bienestar (no-crisis).

    Reglas de contenido (mismas que responses.py): sin diagnóstico, sin
    promesas de confidencialidad, sin frases motivacionales de plantilla.
    Recomendar contactar a la unidad NO es una escalación activa — no
    requiere el consentimiento `wellbeing_escalation_enabled`; es mostrar
    un recurso, igual que las líneas de ayuda.

    NOTA: copy pendiente de revisión por profesional de salud mental
    antes del release público, igual que safety/responses.py.
    """
    if unit_name and unit_phone:
        contact = f"Puedes contactar a {unit_name} al {unit_phone}."
    else:
        contact = render_soft_udd_resources()
    return (
        "Gracias por contármelo — eso merece más apoyo del que yo puedo darte, "
        f"y buscarlo es un buen paso. {contact} "
        "Yo sigo aquí para acompañarte con lo académico cuando quieras."
    )


def build_crisis_aftercare_response() -> str:
    """Acompañamiento para los turnos que SIGUEN a una crisis reciente.

    Mientras dura la ventana de aftercare (ver `orchestrator`), cualquier
    turno que no sea una nueva crisis recibe presencia + recursos, NUNCA
    coaching de estudio ni generación del LLM: alguien que acaba de expresar
    ideación no debe escuchar "estudia 5 minutos" en el turno siguiente.

    Reglas de contenido §4.2.4 (mismas que responses.py): sin diagnóstico,
    sin promesas de confidencialidad, sin motivación de plantilla; siempre
    deriva. No reactiva al contacto de confianza (ya se alertó en la crisis).

    NOTA: copy pendiente de revisión por profesional de salud mental antes
    del release público, igual que safety/responses.py.
    """
    return (
        "Sigo aquí contigo. Lo que me contaste importa y no tienes que "
        "resolverlo ahora ni hacerlo solo. No hace falta que hagas nada más "
        "en este momento. Cuando te sientas listo, contacta a una de estas "
        f"líneas de apoyo. {render_crisis_resources()}"
    )


def _normalize(text: str) -> str:
    text = text.lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()
