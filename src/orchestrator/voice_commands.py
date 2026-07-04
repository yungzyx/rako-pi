"""Comandos de voz locales que se resuelven sin LLM.

Espejo del comando "recuerda que ..." del canal WhatsApp
(`channels/whatsapp/service.py`): el usuario puede dictar una preferencia
por voz y queda en la memoria editable local (sensibilidad normal, igual
que en WhatsApp — el propio usuario la dijo en voz alta).
"""

from __future__ import annotations

# Orden importa: los prefijos más largos primero para que "recuerda que "
# no deje un "que " colgando al matchear "recuerda ". Sinónimos según el
# habla real chilena: "acuérdate", "no olvides", "no te olvides".
_REMEMBER_PREFIXES: tuple[str, ...] = (
    "rako recuerda que ",
    "rako acuerdate de que ",
    "rako acuérdate de que ",
    "rako no te olvides de que ",
    "rako no olvides que ",
    "recuerda que ",
    "acuerdate de que ",
    "acuérdate de que ",
    "no te olvides de que ",
    "no olvides que ",
    "rako recuerda ",
    "rako acuerdate de ",
    "rako acuérdate de ",
    "rako no te olvides de ",
    "recuerda ",
    "acuerdate de ",
    "acuérdate de ",
    "no te olvides de ",
)


def parse_remember_command(transcript: str) -> str | None:
    """Devuelve el texto a recordar si el turno es un comando "recuerda".

    El prefijo se compara en minúsculas pero el texto recordado conserva
    las mayúsculas originales del usuario. Devuelve None si no es comando
    o si no trae contenido.
    """
    clean = " ".join(transcript.strip().split())
    lowered = clean.lower()
    for prefix in _REMEMBER_PREFIXES:
        if lowered.startswith(prefix):
            remainder = clean[len(prefix) :].strip()
            # "recuerda que" a secas matchea el prefijo corto "recuerda "
            # y deja "que" como resto — no es contenido real.
            if not remainder or remainder.lower() == "que":
                return None
            return remainder
    return None
