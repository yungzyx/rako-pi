"""Tests de los wrappers de inputs (botones, PIR, táctil) sobre el bus."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from hardware.buttons import FakeButtons
from hardware.event_bus import InMemoryHardwareEventBus
from hardware.sensors import FakePIR, FakeTouch
from hardware.types import HardwareEvent, HardwareEventKind

UTC = timezone.utc


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def test_fake_buttons_emit_panic_through_bus() -> None:
    bus = InMemoryHardwareEventBus()
    received: list[HardwareEvent] = []
    bus.subscribe(received.append)

    buttons = FakeButtons(bus=bus, now=_now)
    buttons.press_panic()

    assert len(received) == 1
    assert received[0].kind is HardwareEventKind.BUTTON_PANIC
    assert received[0].at == _now()


def test_fake_buttons_emit_emergency_through_bus() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    buttons = FakeButtons(bus=bus, now=_now)
    buttons.press_emergency()

    assert received[0].kind is HardwareEventKind.BUTTON_EMERGENCY


def test_fake_pir_emits_motion() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    pir = FakePIR(bus=bus, now=_now)
    pir.trigger()

    assert received[0].kind is HardwareEventKind.PIR_MOTION


def test_fake_touch_emits_touch() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    bus.subscribe(received.append)

    touch = FakeTouch(bus=bus, now=_now)
    touch.tap()

    assert received[0].kind is HardwareEventKind.TOUCH


def test_panic_button_routes_through_bus_to_subscriber_for_safety() -> None:
    """Smoke test: un botón panic debe llegar al subscriber.

    En producción, el orquestador suscribe un callback que dispara
    safety.panic(). Aquí solo verificamos el cableado.
    """
    bus = InMemoryHardwareEventBus()
    panic_count = 0

    def handler(event: HardwareEvent) -> None:
        nonlocal panic_count
        if event.kind is HardwareEventKind.BUTTON_PANIC:
            panic_count += 1

    bus.subscribe(handler)
    buttons = FakeButtons(bus=bus, now=_now)

    buttons.press_panic()
    buttons.press_emergency()
    buttons.press_panic()

    assert panic_count == 2
