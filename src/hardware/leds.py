"""Controlador de LEDs (anillo NeoPixel + matrices "ojos").

`LEDController` es la API ancha que consume el orquestador. El
`CrisisLightingAdapter` envuelve un `LEDController` para satisfacer el
contrato más estrecho (`set_present_state`) que `safety.protocol`
requiere — así `safety/` no conoce `LEDState`.

La implementación real para la Pi (`NeoPixelLEDController`) carga
`adafruit_circuitpython_neopixel` con lazy import; en CI/dev se usa
`FakeLEDController`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hardware.types import LEDState


@runtime_checkable
class LEDController(Protocol):
    def set_state(self, state: LEDState) -> None: ...
    def turn_off(self) -> None: ...


class FakeLEDController:
    def __init__(self) -> None:
        self.history: list[LEDState] = []
        self.current: LEDState = LEDState.OFF

    def set_state(self, state: LEDState) -> None:
        self.history.append(state)
        self.current = state

    def turn_off(self) -> None:
        self.set_state(LEDState.OFF)


class CrisisLightingAdapter:
    """Bridge de `LEDController` al `_Lighting` Protocol de safety/."""

    def __init__(self, leds: LEDController) -> None:
        self._leds = leds

    def set_present_state(self) -> None:
        self._leds.set_state(LEDState.PRESENT)
