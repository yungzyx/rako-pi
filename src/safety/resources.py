"""Recursos de derivación profesional (UDD + Chile).

Datos públicos. Mantener actualizado y visible sin depender de clicks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HelpResource:
    name: str
    contact: str
    description: str
    available: str


UDD_RESOURCES: tuple[HelpResource, ...] = (
    HelpResource(
        name="Unidad de Convivencia y Salud Mental — Dirección de Bienestar UDD",
        contact="+56 2 2820 3419 | bienestar.apoyoestudiantil@udd.cl | www.bienestarestudiantil.udd.cl",
        description="Orientación y emergencias psicológicas 24/7 para estudiantes.",
        available="24 horas",
    ),
    HelpResource(
        name="CADA UDD — Centro de Apoyo al Desempeño Académico",
        contact="800 200 125 / 800 718 700 | cada.udd.cl",
        description="Apoyo psicopedagógico, gestión del tiempo y bienestar universitario.",
        available="Horario institucional",
    ),
    HelpResource(
        name="SPI — Servicio de Psicología Integral UDD",
        contact=(
            "(56 2) 2327 9278 / (56 2) 2327 9170 | WhatsApp +56 9 8821 9885 | "
            "spi.santiago@udd.cl | psicologia.udd.cl/servicio-de-psicologia-integral"
        ),
        description="Atención psicológica individual.",
        available="Lunes a viernes, 09:00 a 19:00",
    ),
    HelpResource(
        name="VIVE UDD",
        contact="vive.udd.cl/santiago",
        description="Actividades, comunidad, deporte, cultura y liderazgo estudiantil.",
        available="Según calendario UDD",
    ),
)


CHILE_HELPLINES: tuple[HelpResource, ...] = (
    HelpResource(
        name="Salud Responde",
        contact="600 360 7777",
        description="Línea pública del Ministerio de Salud.",
        available="24 horas",
    ),
    HelpResource(
        name="Línea Libre",
        contact="800 200 818",
        description="Apoyo para jóvenes.",
        available="Gratuito",
    ),
    HelpResource(
        name="Hablemos de Todo",
        contact="hablemosdetodo.minsal.cl",
        description="Orientación pública para jóvenes.",
        available="Web",
    ),
    HelpResource(
        name="SAMU",
        contact="131",
        description="Emergencia médica inmediata.",
        available="24 horas",
    ),
)


def render_crisis_resources() -> str:
    return (
        "Contacta ahora a Bienestar UDD: +56 2 2820 3419. "
        "Si hay emergencia inmediata, llama al SAMU: 131. "
        "Mantén estos datos visibles mientras contactas apoyo."
    )


def render_soft_udd_resources() -> str:
    return (
        "Si necesitas hablar con alguien de la UDD, Bienestar UDD está en "
        "+56 2 2820 3419 y CADA UDD en 800 200 125 / 800 718 700."
    )
