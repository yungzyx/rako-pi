"""Tests del event bus de hardware (sensors → orquestador)."""

from __future__ import annotations

from datetime import UTC, datetime

from hardware.event_bus import HardwareEventBus, InMemoryHardwareEventBus
from hardware.types import HardwareEvent, HardwareEventKind

UTC = UTC


def _event(kind: HardwareEventKind = HardwareEventKind.TOUCH) -> HardwareEvent:
    return HardwareEvent(kind=kind, at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC))


def test_inmemory_bus_satisfies_protocol() -> None:
    bus: HardwareEventBus = InMemoryHardwareEventBus()

    assert hasattr(bus, "subscribe")


def test_subscribers_receive_emitted_events() -> None:
    bus = InMemoryHardwareEventBus()
    received = []

    bus.subscribe(received.append)
    bus.emit(_event(HardwareEventKind.BUTTON_PANIC))

    assert len(received) == 1
    assert received[0].kind is HardwareEventKind.BUTTON_PANIC


def test_multiple_subscribers_all_receive_events() -> None:
    bus = InMemoryHardwareEventBus()
    a, b = [], []
    bus.subscribe(a.append)
    bus.subscribe(b.append)

    bus.emit(_event())

    assert len(a) == 1 and len(b) == 1


def test_unsubscribe_stops_delivery() -> None:
    bus = InMemoryHardwareEventBus()
    received = []
    handle = bus.subscribe(received.append)

    bus.unsubscribe(handle)
    bus.emit(_event())

    assert received == []


def test_unsubscribe_unknown_handle_is_no_op() -> None:
    bus = InMemoryHardwareEventBus()
    bus.unsubscribe_id(99999)  # debe no levantar


def test_callback_exception_does_not_break_other_subscribers() -> None:
    bus = InMemoryHardwareEventBus()
    received_b = []

    def bad(_e):
        raise RuntimeError("subscriber crashed")

    bus.subscribe(bad)
    bus.subscribe(received_b.append)

    bus.emit(_event())

    assert len(received_b) == 1
