"""Detección de preferencias dichas al pasar — para aprendizaje OPT-IN.

Rako nunca aprende en silencio: si el usuario menciona una preferencia de
estudio en la conversación, el dispositivo PREGUNTA si quiere guardarla y
solo la persiste tras un "sí, recuérdalo" explícito (TurnSession).

Los patrones son deliberadamente acotados a rutinas/preferencias de
estudio — nada emocional ni personal se captura por esta vía.
"""

from __future__ import annotations

_PREFERENCE_PATTERNS: tuple[str, ...] = (
    "prefiero ",
    "me funciona ",
    "siempre estudio ",
    "estudio mejor ",
    "me concentro mejor ",
    "me rinde más ",
    "me rinde mas ",
)

_MIN_PREFERENCE_CHARS = 12
_MAX_PREFERENCE_CHARS = 120


def extract_preference(transcript: str) -> str | None:
    """Frase de preferencia contenida en el turno, o None.

    Devuelve el texto desde el patrón hasta el final de la frase, con el
    casing original del usuario.
    """
    clean = " ".join(transcript.strip().split())
    lowered = clean.lower()
    for pattern in _PREFERENCE_PATTERNS:
        index = lowered.find(pattern)
        if index == -1:
            continue
        candidate = clean[index:].strip().rstrip(".!?¡¿,;")
        if _MIN_PREFERENCE_CHARS <= len(candidate) <= _MAX_PREFERENCE_CHARS:
            return candidate
    return None
