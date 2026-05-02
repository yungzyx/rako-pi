"""NeoPixel LED controller para la Pi.

`NeoPixelLEDController` es testeable: recibe cualquier objeto compatible
con la API de `neopixel.NeoPixel` (`__len__`, `__setitem__`, `show()`).

`create_pi_neopixel_controller` lazy-importa
`adafruit_circuitpython_neopixel` + `board` y construye un controlador
real para la Pi.
"""

from __future__ import annotations

from typing import Any, Final

from hardware.types import LEDState

# Mapeo estado → color RGB. Tonos cálidos para PRESENT / ALERT_SOFT
# (estado del protocolo de crisis y nudge proactivo); fríos para
# escucha / pensamiento.
_COLORS: Final[dict[LEDState, tuple[int, int, int]]] = {
    LEDState.OFF: (0, 0, 0),
    LEDState.LISTENING: (0, 30, 100),
    LEDState.THINKING: (50, 30, 80),
    LEDState.SPEAKING: (0, 80, 40),
    LEDState.PRESENT: (90, 50, 20),
    LEDState.ALERT_SOFT: (110, 60, 0),
}


class NeoPixelLEDController:
    def __init__(self, pixels: Any) -> None:
        self._pixels = pixels

    def set_state(self, state: LEDState) -> None:
        color = _COLORS[state]
        for i in range(len(self._pixels)):
            self._pixels[i] = color
        self._pixels.show()

    def turn_off(self) -> None:
        self.set_state(LEDState.OFF)


def create_pi_neopixel_controller(  # pragma: no cover - Pi only
    *, pin: int, count: int, brightness: float = 0.3
) -> NeoPixelLEDController:
    """Factory para la Pi. Lazy-importa adafruit_circuitpython_neopixel."""
    import board  # type: ignore[import-not-found]
    import neopixel  # type: ignore[import-not-found]

    pixels = neopixel.NeoPixel(
        getattr(board, f"D{pin}"),
        count,
        brightness=brightness,
        auto_write=False,
    )
    return NeoPixelLEDController(pixels)
