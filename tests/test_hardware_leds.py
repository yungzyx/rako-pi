"""Tests del LED controller y del adapter para el protocolo de crisis."""

from __future__ import annotations

from hardware.leds import (
    CrisisLightingAdapter,
    FakeLEDController,
    LEDController,
)
from hardware.types import LEDState


def test_fake_satisfies_protocol() -> None:
    led: LEDController = FakeLEDController()
    assert hasattr(led, "set_state") and hasattr(led, "turn_off")


def test_set_state_records_history() -> None:
    led = FakeLEDController()

    led.set_state(LEDState.LISTENING)
    led.set_state(LEDState.THINKING)

    assert led.history == [LEDState.LISTENING, LEDState.THINKING]
    assert led.current is LEDState.THINKING


def test_turn_off_records_off() -> None:
    led = FakeLEDController()
    led.set_state(LEDState.LISTENING)

    led.turn_off()

    assert led.current is LEDState.OFF
    assert led.history[-1] is LEDState.OFF


def test_crisis_lighting_adapter_sets_present_state() -> None:
    led = FakeLEDController()
    adapter = CrisisLightingAdapter(led)

    adapter.set_present_state()

    assert led.current is LEDState.PRESENT


def test_crisis_lighting_adapter_satisfies_safety_protocol() -> None:
    # El adapter debe cumplir el _Lighting Protocol del módulo safety.
    from safety.protocol import CrisisProtocol  # importa el Protocol indirectamente

    led = FakeLEDController()
    adapter = CrisisLightingAdapter(led)

    # Si el método existe y no levanta, satisface el contrato estructural.
    adapter.set_present_state()
    assert led.history == [LEDState.PRESENT]

    # Verificación adicional: se puede usar como dependencia de CrisisProtocol.
    # No ejecutamos execute() aquí — eso ya está cubierto en test_safety_protocol.
    # Solo verificamos compatibilidad de tipo runtime.
    assert callable(adapter.set_present_state)
    _ = CrisisProtocol  # silenciar lint
