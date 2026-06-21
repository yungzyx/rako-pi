"""Pilot checklist for validating Rako with real university students."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

PilotPriority = Literal["must", "should", "later"]


@dataclass(frozen=True, slots=True)
class PilotStep:
    area: str
    name: str
    priority: PilotPriority
    success_metric: str
    action: str


@dataclass(frozen=True, slots=True)
class PilotPlan:
    recommended_users: str
    duration_days: int
    steps: tuple[PilotStep, ...]


def build_pilot_plan() -> PilotPlan:
    return PilotPlan(
        recommended_users="3-5",
        duration_days=14,
        steps=(
            PilotStep(
                "setup",
                "placa limpia",
                "must",
                "setup completo en menos de 15 minutos",
                "flashear, rako-install, rako-first-run, /setup",
            ),
            PilotStep(
                "audio",
                "conversación real",
                "must",
                ">= 8 de 10 turnos entendidos",
                "probar micrófono/parlante en escritorio real",
            ),
            PilotStep(
                "academia",
                "bloques de foco",
                "must",
                ">= 3 bloques iniciados por usuario/semana",
                "medir si Rako reduce fricción de partida",
            ),
            PilotStep(
                "whatsapp",
                "seguimiento visible",
                "should",
                "usuario entiende resumen diario",
                "activar check-ins y reportes con consentimiento",
            ),
            PilotStep(
                "ojos",
                "cercanía",
                "should",
                "usuario reconoce escuchando/pensando/hablando",
                "observar expresiones sin explicar la UI",
            ),
            PilotStep(
                "soporte",
                "diagnóstico",
                "must",
                "support bundle permite entender bloqueo",
                "generar bundle ante cada problema",
            ),
            PilotStep(
                "seguridad",
                "crisis y privacidad",
                "must",
                "sin improvisación del LLM en crisis",
                "probar frase demo y borrado/exportación",
            ),
        ),
    )


def pilot_plan_to_dict(plan: PilotPlan) -> dict[str, Any]:
    return {
        "recommended_users": plan.recommended_users,
        "duration_days": plan.duration_days,
        "steps": [asdict(step) for step in plan.steps],
    }
