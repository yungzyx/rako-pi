"""Academic-scope guardrails for Rako.

Rako is an academic companion, not a mental-health assistant. These helpers keep
non-crisis clinical topics out of the LLM path and redirect to UDD resources.
"""

from __future__ import annotations

import re
import unicodedata

from safety.resources import render_soft_udd_resources

_HEALTH_TOPIC_PATTERNS = (
    "depresion",
    "deprimido",
    "deprimida",
    "ansiedad",
    "ansioso",
    "ansiosa",
    "trauma",
    "duelo",
    "terapia",
    "terapeuta",
    "psicologo",
    "psicologa",
    "psiquiatra",
    "medicamento",
    "antidepresivo",
    "diagnostico",
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


def _normalize(text: str) -> str:
    text = text.lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()
