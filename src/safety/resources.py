"""Recursos de derivación profesional (Chile).

Datos públicos. Mantener actualizado. Cuando se valide con profesional
y se sumen líneas regionales, extender la tupla.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HelpResource:
    name: str
    contact: str
    description: str
    available: str


CHILE_HELPLINES: tuple[HelpResource, ...] = (
    HelpResource(
        name="Salud Responde",
        contact="600 360 7777",
        description="Línea pública del Ministerio de Salud, atención en salud mental.",
        available="24 horas",
    ),
    HelpResource(
        name="*4141 Salud Mental",
        contact="*4141",
        description="Línea de prevención del suicidio desde teléfonos móviles.",
        available="24 horas",
    ),
    HelpResource(
        name="Línea Libre",
        contact="1515",
        description="Apoyo psicológico para niños, niñas y jóvenes (4-24 años).",
        available="Lun-Dom 11:00-23:00",
    ),
    HelpResource(
        name="Fono Drogas y Alcohol",
        contact="1412",
        description="Orientación frente a consumo problemático.",
        available="24 horas",
    ),
)
