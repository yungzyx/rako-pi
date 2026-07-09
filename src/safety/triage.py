"""Triage graduado para turnos SIN crisis.

El detector de crisis (`safety.detector`) corre PRIMERO y es inapelable.
Este módulo decide qué hacer con todo lo demás — diferenciar entre:

- pedir consejo clínico (fuera del rol de Rako → redirección),
- revelar algo personal de salud mental (→ derivar a la unidad de
  bienestar, con calidez y sin diagnóstico),
- mencionar ansiedad/estrés en un marco académico puntual (→ el LLM puede
  acompañar, con una nota de tono),
- un patrón de ánimo bajo sostenido en la semana (→ derivar aunque la
  frase suene liviana),
- conversación normal (→ LLM sin más).

Igual que el detector: determinístico, sin efectos, auditable línea por
línea. Sin matching difuso — cada frase agregada acá es una decisión
revisable en code review.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Final

from safety.scope import mentions_mental_health_topic

# Días distintos con ánimo bajo (autoreporte WhatsApp u otra fuente local)
# dentro de la última semana a partir de los cuales una mención emocional
# deja de tratarse como puntual y pasa a derivación.
RECURRENCE_LOW_MOOD_DAYS: Final = 3


class TriageLevel(Enum):
    ACADEMIC = "ACADEMIC"
    SUPPORTIVE_ACADEMIC = "SUPPORTIVE_ACADEMIC"
    ELEVATED_SUPPORT = "ELEVATED_SUPPORT"
    WELLBEING_REFERRAL = "WELLBEING_REFERRAL"
    CLINICAL_SCOPE = "CLINICAL_SCOPE"


@dataclass(frozen=True, slots=True)
class TriageResult:
    level: TriageLevel
    reason: str


# Pedidos de consejo clínico (medicación, dosis, diagnóstico). Siempre
# fuera de rol, sin importar el marco.
_CLINICAL_ADVICE_PATTERNS: Final[tuple[str, ...]] = (
    "que medicamento",
    "que pastilla",
    "que remedio",
    "que dosis",
    "deberia tomar",
    "puedo tomar",
    "puedo dejar de tomar",
    "dejar de tomar mi",
    "me recetas",
    "sera que tengo",
    "que trastorno tengo",
)

# Revelación personal fuerte: diagnóstico, tratamiento o búsqueda activa
# de ayuda profesional. Deriva siempre, incluso con marco académico.
_STRONG_PERSONAL_PATTERNS: Final[tuple[str, ...]] = (
    "me diagnosticaron",
    "estoy en tratamiento",
    "sufro de",
    "necesito terapia",
    "necesito un psicologo",
    "necesito una psicologa",
    "necesito ayuda psicologica",
    "quiero terapia",
    "quiero ir al psicologo",
    "quiero ir a la psicologa",
)

# Revelación personal débil: primera persona + tema clínico, sin marco
# de tratamiento. Con marco académico se trata como estrés puntual.
_WEAK_PERSONAL_PATTERNS: Final[tuple[str, ...]] = (
    "creo que tengo",
    "tengo ansiedad",
    "tengo depresion",
    "tengo un trastorno",
    "mi ansiedad",
    "mi depresion",
    "estoy deprimido",
    "estoy deprimida",
    "estoy con ansiedad",
    "me da ansiedad",
)

# Malestar emocional dicho sin vocabulario clínico. El LLM puede acompañar
# con una nota de tono; la recurrencia lo sube a derivación.
_EMOTIONAL_DISTRESS_PATTERNS: Final[tuple[str, ...]] = (
    "me siento muy solo",
    "me siento muy sola",
    "me siento solo",
    "me siento sola",
    "no me dan ganas de nada",
    "no tengo ganas",
    "no quiero trabajar",
    "nervioso",
    "nerviosa",
    "lo estoy pasando muy mal",
    "lo estoy pasando mal",
    "estoy llorando",
)

# Marcadores de contexto académico puntual (prueba, ramo, plazo).
_ACADEMIC_FRAME_PATTERNS: Final[tuple[str, ...]] = (
    "prueba",
    "examen",
    "certamen",
    "semestre",
    "ramo",
    "tarea",
    "clase",
    "presentacion",
    "nota",
    "informe",
    "entrega",
    "estudiar",
)


def triage_turn(
    transcript: str,
    *,
    recent_low_mood_days: int = 0,
    elevated: bool = False,
) -> TriageResult:
    """Clasifica un turno no-crisis. Determinístico, sin efectos.

    `recent_low_mood_days`: días distintos con ánimo bajo en la última
    semana (0 si no hay datos). `elevated`: veredicto ELEVATED del
    detector de crisis para este turno.
    """
    normalized = _normalize(transcript)
    recurring = recent_low_mood_days >= RECURRENCE_LOW_MOOD_DAYS

    if _matches_any(normalized, _CLINICAL_ADVICE_PATTERNS):
        return TriageResult(TriageLevel.CLINICAL_SCOPE, "clinical_advice_request")
    if _matches_any(normalized, _STRONG_PERSONAL_PATTERNS):
        return TriageResult(TriageLevel.WELLBEING_REFERRAL, "personal_disclosure")

    weak_personal = _matches_any(normalized, _WEAK_PERSONAL_PATTERNS)
    distress = _matches_any(normalized, _EMOTIONAL_DISTRESS_PATTERNS)
    academic_frame = _matches_any(normalized, _ACADEMIC_FRAME_PATTERNS)

    if weak_personal and not academic_frame:
        return TriageResult(TriageLevel.WELLBEING_REFERRAL, "personal_disclosure")
    if (weak_personal and academic_frame) or distress:
        if recurring:
            return TriageResult(TriageLevel.WELLBEING_REFERRAL, "recurring_low_mood")
        return TriageResult(TriageLevel.SUPPORTIVE_ACADEMIC, "academic_stress_mention")
    if mentions_mental_health_topic(transcript):
        return TriageResult(TriageLevel.CLINICAL_SCOPE, "clinical_topic_out_of_scope")
    if elevated:
        if recurring:
            return TriageResult(TriageLevel.WELLBEING_REFERRAL, "sustained_low_mood")
        return TriageResult(TriageLevel.ELEVATED_SUPPORT, "elevated_state")
    return TriageResult(TriageLevel.ACADEMIC, "academic")


def _normalize(text: str) -> str:
    text = text.lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


def _matches_any(normalized_text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in normalized_text for pattern in patterns)
