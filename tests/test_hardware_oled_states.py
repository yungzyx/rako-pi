from __future__ import annotations

from hardware.oled_states import RakoVisualState, expression_for_state, state_for_turn_phase


def test_expression_for_state_maps_core_runtime_states() -> None:
    assert expression_for_state(RakoVisualState.LISTENING) == "listening"
    assert expression_for_state(RakoVisualState.THINKING) == "thinking"
    assert expression_for_state(RakoVisualState.SPEAKING) == "speaking"
    assert expression_for_state(RakoVisualState.USER_INACTIVE) == "sleepy"


def test_state_for_turn_phase_normalizes_common_names() -> None:
    assert state_for_turn_phase("recording") is RakoVisualState.LISTENING
    assert state_for_turn_phase("rag") is RakoVisualState.THINKING
    assert state_for_turn_phase("playback") is RakoVisualState.SPEAKING
    assert state_for_turn_phase("pomodoro") is RakoVisualState.FOCUS_RUNNING
