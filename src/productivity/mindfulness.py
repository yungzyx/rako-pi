"""Short mindfulness exercises Rako can guide by voice or WhatsApp.

These are not clinical interventions. They are short, low-risk practices for
study breaks, inspired by common mindfulness guidance: breath awareness, body
scan, mindful walking, and gentle stretch/breathe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

MindfulnessExerciseId = Literal[
    "one_minute_breath",
    "three_breath_reset",
    "body_scan_short",
    "mindful_walking",
    "stretch_and_breathe",
]


@dataclass(frozen=True, slots=True)
class MindfulnessExercise:
    id: MindfulnessExerciseId
    title: str
    minutes: int
    context: str
    script: tuple[str, ...]

    @property
    def prompt(self) -> str:
        return " ".join(self.script)


_EXERCISES: tuple[MindfulnessExercise, ...] = (
    MindfulnessExercise(
        id="three_breath_reset",
        title="Tres respiraciones",
        minutes=1,
        context="quick_reset",
        script=(
            "Hagamos tres respiraciones lentas.",
            "Inhala suave por la nariz.",
            "Exhala más lento de lo que inhalaste.",
            "Repite dos veces más y vuelve solo al siguiente paso.",
        ),
    ),
    MindfulnessExercise(
        id="one_minute_breath",
        title="Un minuto de respiración",
        minutes=1,
        context="before_focus",
        script=(
            "Siéntate cómodo y deja los hombros un poco más bajos.",
            "Lleva la atención al aire entrando y saliendo.",
            "Si aparece un pensamiento, nótalo y vuelve a la respiración.",
            "No hay que hacerlo perfecto; solo volver.",
        ),
    ),
    MindfulnessExercise(
        id="body_scan_short",
        title="Escaneo corporal corto",
        minutes=3,
        context="low_mood",
        script=(
            "Lleva la atención a los pies, después a las piernas y luego al pecho.",
            "Nota si hay tensión, calor, presión o cansancio.",
            "No intentes cambiarlo todo; solo reconoce lo que está ahí.",
            "Suelta la mandíbula y vuelve con una exhalación lenta.",
        ),
    ),
    MindfulnessExercise(
        id="mindful_walking",
        title="Caminata consciente",
        minutes=5,
        context="rest_break",
        script=(
            "Camina lento por un lugar seguro.",
            "Nota el contacto de los pies con el suelo.",
            "Mira un detalle real del entorno y vuelve al cuerpo.",
            "Cuando termines, elige una acción pequeña para continuar.",
        ),
    ),
    MindfulnessExercise(
        id="stretch_and_breathe",
        title="Estirar y respirar",
        minutes=2,
        context="after_focus",
        script=(
            "Estira cuello y hombros sin forzar.",
            "Inhala mientras alargas la espalda.",
            "Exhala y suelta un poco la tensión.",
            "Si algo duele o incomoda, detente y vuelve a una postura neutra.",
        ),
    ),
)


def list_mindfulness_exercises() -> tuple[MindfulnessExercise, ...]:
    return _EXERCISES


def get_mindfulness_exercise(id: MindfulnessExerciseId) -> MindfulnessExercise:
    for exercise in _EXERCISES:
        if exercise.id == id:
            return exercise
    raise KeyError(f"unknown mindfulness exercise: {id}")


def pick_mindfulness_exercise(
    *,
    context: str | None = None,
    max_minutes: int | None = None,
) -> MindfulnessExercise:
    candidates = _EXERCISES
    if context is not None:
        context_matches = tuple(ex for ex in candidates if ex.context == context)
        if context_matches:
            candidates = context_matches
    if max_minutes is not None:
        duration_matches = tuple(ex for ex in candidates if ex.minutes <= max_minutes)
        if duration_matches:
            candidates = duration_matches
    return candidates[0]


def mindfulness_exercise_to_dict(exercise: MindfulnessExercise) -> dict[str, object]:
    return asdict(exercise)
