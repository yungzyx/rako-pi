"""Safe demo mode checklist and canned profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DemoMode:
    ready: bool
    commands: tuple[str, ...]
    script: tuple[str, ...]
    safety_notes: tuple[str, ...]


def build_demo_mode() -> DemoMode:
    return DemoMode(
        ready=True,
        commands=(
            "./scripts/rako-first-run --name Demo --wifi-ssid Demo --memory 'Prefiere bloques cortos'",
            "./scripts/rako-demo --no-playback",
            "./scripts/rako.sh demo-crisis-panic",
        ),
        script=(
            "Usuario: Rako, ayúdame a partir con cálculo.",
            "Rako: propone un bloque pequeño, una tarea concreta y cierre de progreso.",
            "Usuario: me siento sobrepasado.",
            "Rako: responde con contención y límites seguros, sin terapia improvisada.",
        ),
        safety_notes=(
            "No usar números reales de WhatsApp en demos públicas.",
            "No mostrar memoria ni soporte bundle de usuarios reales.",
            "Crisis demo debe usar respuestas curadas y bypass del LLM.",
        ),
    )


def demo_mode_to_dict(demo: DemoMode) -> dict[str, Any]:
    payload = asdict(demo)
    return {
        key: list(value) if isinstance(value, tuple) else value for key, value in payload.items()
    }
