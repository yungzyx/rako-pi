"""Clasificación y registro de ánimo autoreportado por WhatsApp."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from db.database import Database
from db.types import EmotionalStateRecord
from emotion.types import EmotionalVector


def classify_mood(text: str) -> str | None:
    lowered = text.lower()
    if any(word in lowered for word in ("mal", "bajo", "baja", "triste", "agotado", "agotada")):
        return "low"
    if any(
        word in lowered
        for word in ("normal", "neutro", "ok", "ahi", "ahí", "mas o menos", "más o menos")
    ):
        return "neutral"
    if any(word in lowered for word in ("bien", "motivado", "motivada", "tranquilo", "tranquila")):
        return "good"
    return None


def store_mood(db: Database, *, mood: str, now: datetime) -> None:
    db.emotional_states.append(
        EmotionalStateRecord(
            id=f"wa_{uuid4().hex}",
            at=now,
            vector=mood_vector(mood),
            trigger_event="whatsapp_checkin",
            confidence=0.7,
        )
    )


def mood_vector(mood: str) -> EmotionalVector:
    if mood == "low":
        return EmotionalVector(valence=-0.55, arousal=0.55, dominance=0.35)
    if mood == "good":
        return EmotionalVector(valence=0.55, arousal=0.35, dominance=0.65)
    return EmotionalVector(valence=0.0, arousal=0.3, dominance=0.5)


def mood_response(mood: str) -> str:
    if mood == "low":
        return "Gracias por decirme. Bajemos la exigencia: ¿te sirve partir con 10 minutos suaves?"
    if mood == "good":
        return "Bien. Aprovechemos esa energía con un bloque corto y claro cuando quieras."
    return "Gracias. Podemos ir paso a paso; dime si quieres estudiar, descansar o planear."
