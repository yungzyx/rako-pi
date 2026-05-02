"""Respuestas pre-curadas para situaciones de crisis.

El texto de cada respuesta NO se sintetiza en vivo: se rendiriza una vez
con TTS (offline) y queda en `src/safety/prerecorded/{id}.wav`. Así no
dependemos de internet en el peor momento.

El contenido de aquí es un punto de partida MVP escrito en línea con la
guía del documento de arquitectura (presencia, no soluciones; nada de
diagnósticos ni motivación vacía). Antes de release público debe ser
revisado y validado por un profesional de salud mental.
"""

from __future__ import annotations

from dataclasses import dataclass

from safety.types import CrisisLevel, CrisisReason, CrisisSignal


@dataclass(frozen=True, slots=True)
class CrisisResponse:
    id: str
    text: str
    audio_path: str
    activates_trusted_contact: bool


_PRERECORDED_DIR = "src/safety/prerecorded"


def _prerecorded(id_: str) -> str:
    return f"{_PRERECORDED_DIR}/{id_}.wav"


_RESPONSES: dict[str, CrisisResponse] = {
    "ideation": CrisisResponse(
        id="ideation",
        text=(
            "Estoy aquí contigo. Lo que estás sintiendo es real y no "
            "tienes que estar solo en esto. Voy a avisar a tu persona "
            "de confianza para que esté contigo, y te dejo a la mano una "
            "línea de ayuda. ¿Puedes quedarte conmigo un momento?"
        ),
        audio_path=_prerecorded("ideation"),
        activates_trusted_contact=True,
    ),
    "selfharm": CrisisResponse(
        id="selfharm",
        text=(
            "Te escucho. Lo que sientes ahora es muy difícil. Estoy aquí "
            "contigo. Voy a avisar a tu persona de confianza para que "
            "esté contigo, y te muestro recursos para que no estés solo "
            "en este momento."
        ),
        audio_path=_prerecorded("selfharm"),
        activates_trusted_contact=True,
    ),
    "panic": CrisisResponse(
        id="panic",
        text=(
            "Estoy contigo. Respira a tu ritmo. Voy a avisar a tu "
            "persona de confianza ahora mismo. No te tienes que ir a "
            "ningún lado, yo me quedo aquí."
        ),
        audio_path=_prerecorded("panic"),
        activates_trusted_contact=True,
    ),
    "sustained_distress": CrisisResponse(
        id="sustained_distress",
        text=(
            "Te he sentido muy cargado este rato. No tienes que "
            "explicarme nada. Estoy aquí. Si quieres, le aviso a tu "
            "persona de confianza para que te acompañe."
        ),
        audio_path=_prerecorded("sustained_distress"),
        activates_trusted_contact=True,
    ),
    "inactivity_followup": CrisisResponse(
        id="inactivity_followup",
        text=(
            "Hola. Hace un rato te sentí mal y desde entonces ha estado "
            "todo en silencio. Solo quería estar acá por si me "
            "necesitas. No tienes que responder ahora."
        ),
        audio_path=_prerecorded("inactivity_followup"),
        activates_trusted_contact=False,
    ),
}


# Prioridad: motivos de mayor severidad ganan al elegir UNA respuesta.
_REASON_PRIORITY: tuple[tuple[CrisisReason, str], ...] = (
    (CrisisReason.KEYWORDS_IDEATION, "ideation"),
    (CrisisReason.KEYWORDS_SELFHARM, "selfharm"),
    (CrisisReason.PANIC_BUTTON_PHYSICAL, "panic"),
    (CrisisReason.PANIC_BUTTON_APP, "panic"),
    (CrisisReason.SUSTAINED_EMOTIONAL_EXTREME, "sustained_distress"),
    (CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS, "inactivity_followup"),
)


def pick_response(signal: CrisisSignal) -> CrisisResponse:
    """Selecciona la respuesta curada para la señal dada.

    Solo válido para `CrisisLevel.CRISIS`.
    """
    if signal.level is not CrisisLevel.CRISIS:
        raise ValueError(f"pick_response requires CRISIS level, got {signal.level.name}")

    reasons_set = set(signal.reasons)
    for reason, response_id in _REASON_PRIORITY:
        if reason in reasons_set:
            return _RESPONSES[response_id]

    # Fallback defensivo — un signal CRISIS sin razones reconocidas no
    # debería ocurrir, pero si ocurre, respondemos con presencia segura.
    return _RESPONSES["sustained_distress"]
