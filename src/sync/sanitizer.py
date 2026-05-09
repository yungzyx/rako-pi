"""Sanitizador de payloads — last line of defense antes del wire.

Aplica al `payload` de todo `SyncEvent` antes de encolar. Garantías:

- Drop de claves sensibles (PII, emocionales, audio/transcripción).
- Drop de valores no-primitivos (sin nested dicts ni listas — un objeto
  arbitrario no puede colarse al wire vía un campo legítimo).
- Cap de strings (500 chars) para limitar superficie de PII en
  payloads de texto libre.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from sync.types import PrimitiveValue

_MAX_STRING_LEN: Final[int] = 500

_DENIED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "transcript",
        "transcription_excerpt",
        "transcription",
        "audio",
        "audio_path",
        "audio_data",
        "valence",
        "arousal",
        "dominance",
        "emotion",
        "emotion_vector",
        "name",
        "real_name",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address",
        "ip_address",
        "ssn",
        "rut",
        "password",
        "token",
        "api_key",
    }
)


def sanitize_payload(payload: Mapping[str, object]) -> dict[str, PrimitiveValue]:
    out: dict[str, PrimitiveValue] = {}
    for key, value in payload.items():
        if key.lower() in _DENIED_KEYS:
            continue
        if not _is_primitive(value):
            continue
        if isinstance(value, str) and len(value) > _MAX_STRING_LEN:
            value = value[:_MAX_STRING_LEN]
        out[key] = value  # type: ignore[assignment]
    return out


def _is_primitive(value: object) -> bool:
    return isinstance(value, str | int | float | bool) or value is None
