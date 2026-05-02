"""Tests de los wrappers reales de inputs (botones, PIR, táctil)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from hardware.buttons_real import GpioZeroButtons
from hardware.event_bus import InMemoryHardwareEventBus
from hardware.sensors_real import GpioZeroPIR, GpioZeroTouch
from hardware.types import HardwareEventKind


class _FakeButton:
    """Mimic gpiozero.Button: when_pressed callable assignment."""

    def __init__(self) -> None:
        self.when_pressed: Callable[[], None] | None = None

    def fire(self) -> None:
        if self.when_pressed:
            self.when_pressed()


class _FakeMotionSensor:
    def __init__(self) -> None:
        self.when_motion: Callable[[], None] | None = None

    def fire(self) -> None:
        if self.when_motion:
            self.when_motion()


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def test_panic_button_emits_event_through_bus() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    panic = _FakeButton()
    emergency = _FakeButton()
    GpioZeroButtons(panic_button=panic, emergency_button=emergency, bus=bus, now=_now)

    panic.fire()

    assert len(received) == 1
    assert received[0].kind is HardwareEventKind.BUTTON_PANIC
    assert received[0].at == _now()


def test_emergency_button_emits_event_through_bus() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    panic = _FakeButton()
    emergency = _FakeButton()
    GpioZeroButtons(panic_button=panic, emergency_button=emergency, bus=bus, now=_now)

    emergency.fire()

    assert received[0].kind is HardwareEventKind.BUTTON_EMERGENCY


def test_pir_emits_motion_event() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    sensor = _FakeMotionSensor()
    GpioZeroPIR(motion_sensor=sensor, bus=bus, now=_now)

    sensor.fire()

    assert received[0].kind is HardwareEventKind.PIR_MOTION


def test_touch_emits_touch_event() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    touch_input = _FakeButton()  # capacitive sensor exposes Button-like API
    GpioZeroTouch(touch_input=touch_input, bus=bus, now=_now)

    touch_input.fire()

    assert received[0].kind is HardwareEventKind.TOUCH


def test_multiple_button_presses_emit_multiple_events() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    panic = _FakeButton()
    emergency = _FakeButton()
    GpioZeroButtons(panic_button=panic, emergency_button=emergency, bus=bus, now=_now)

    panic.fire()
    panic.fire()
    emergency.fire()

    assert [e.kind for e in received] == [
        HardwareEventKind.BUTTON_PANIC,
        HardwareEventKind.BUTTON_PANIC,
        HardwareEventKind.BUTTON_EMERGENCY,
    ]
