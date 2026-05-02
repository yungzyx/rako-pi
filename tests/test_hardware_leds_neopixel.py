"""Tests del NeoPixelLEDController (wrapper inyectable)."""

from __future__ import annotations

from hardware.leds_neopixel import NeoPixelLEDController
from hardware.types import LEDState


class _FakePixels:
    """Mimic neopixel.NeoPixel: __len__, __setitem__, show."""

    def __init__(self, n: int) -> None:
        self._buffer: list[tuple[int, int, int]] = [(0, 0, 0)] * n
        self.show_calls = 0

    def __len__(self) -> int:
        return len(self._buffer)

    def __setitem__(self, idx: int, value: tuple[int, int, int]) -> None:
        self._buffer[idx] = value

    def show(self) -> None:
        self.show_calls += 1


def test_set_state_paints_all_pixels_and_shows() -> None:
    pixels = _FakePixels(n=12)
    led = NeoPixelLEDController(pixels)

    led.set_state(LEDState.LISTENING)

    assert pixels.show_calls == 1
    # Todos los pixels deben tener el mismo color (no negro).
    colors = {pixels._buffer[i] for i in range(12)}
    assert len(colors) == 1
    assert next(iter(colors)) != (0, 0, 0)


def test_different_states_produce_different_colors() -> None:
    pixels = _FakePixels(n=4)
    led = NeoPixelLEDController(pixels)

    led.set_state(LEDState.LISTENING)
    listening_color = pixels._buffer[0]

    led.set_state(LEDState.PRESENT)
    present_color = pixels._buffer[0]

    led.set_state(LEDState.SPEAKING)
    speaking_color = pixels._buffer[0]

    assert listening_color != present_color
    assert listening_color != speaking_color
    assert present_color != speaking_color


def test_turn_off_blacks_out_all_pixels() -> None:
    pixels = _FakePixels(n=4)
    led = NeoPixelLEDController(pixels)
    led.set_state(LEDState.SPEAKING)

    led.turn_off()

    for i in range(4):
        assert pixels._buffer[i] == (0, 0, 0)


def test_every_led_state_has_a_color_mapping() -> None:
    pixels = _FakePixels(n=1)
    led = NeoPixelLEDController(pixels)

    # No debe levantar para ningún LEDState.
    for state in LEDState:
        led.set_state(state)
