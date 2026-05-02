"""Tipos compartidos del módulo de emoción.

`EmotionalVector` es la salida canónica del SER y la entrada que
consume `safety/`. Convención de rangos:

- `valence`   ∈ [-1, 1]  (negativo = displacentero, positivo = placentero)
- `arousal`   ∈ [ 0, 1]  (0 = calmo, 1 = altamente activado)
- `dominance` ∈ [ 0, 1]  (0 = sumiso, 1 = en control)

Mantener `frozen=True` siempre. Los productores deben hacer clamp antes
de instanciar (no relajamos los rangos aquí).
"""

from __future__ import annotations

from dataclasses import dataclass

_VALENCE_MIN = -1.0
_VALENCE_MAX = 1.0
_UNIT_MIN = 0.0
_UNIT_MAX = 1.0


@dataclass(frozen=True, slots=True)
class EmotionalVector:
    valence: float
    arousal: float
    dominance: float

    def __post_init__(self) -> None:
        if not _VALENCE_MIN <= self.valence <= _VALENCE_MAX:
            raise ValueError(f"valence out of range [-1, 1]: {self.valence!r}")
        if not _UNIT_MIN <= self.arousal <= _UNIT_MAX:
            raise ValueError(f"arousal out of range [0, 1]: {self.arousal!r}")
        if not _UNIT_MIN <= self.dominance <= _UNIT_MAX:
            raise ValueError(f"dominance out of range [0, 1]: {self.dominance!r}")
