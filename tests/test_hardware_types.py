"""Tests de los tipos del módulo hardware."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hardware.types import HardwareEvent, HardwareEventKind, LEDState


def test_led_state_values_are_unique() -> None:
    values = {s.value for s in LEDState}

    assert len(values) == len(LEDState)
    assert "OFF" in values
    assert "PRESENT" in values  # usado por el protocolo de crisis


def test_hardware_event_kind_covers_required_inputs() -> None:
    kinds = {k.name for k in HardwareEventKind}

    assert {"PIR_MOTION", "TOUCH", "BUTTON_PANIC", "BUTTON_EMERGENCY"} <= kinds


def test_hardware_event_is_immutable() -> None:
    event = HardwareEvent(
        kind=HardwareEventKind.BUTTON_PANIC,
        at=datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(Exception):
        event.kind = HardwareEventKind.TOUCH  # type: ignore[misc]
