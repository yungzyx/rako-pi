from __future__ import annotations

from hardware.oled_states import (
    RakoVisualState,
    expression_for_state,
    state_for_turn_phase,
    visual_profile_for_state,
)


def test_expression_for_state_maps_core_runtime_states() -> None:
    assert expression_for_state(RakoVisualState.READY) == "neutral"
    assert expression_for_state(RakoVisualState.LISTENING) == "listening"
    assert expression_for_state(RakoVisualState.THINKING) == "thinking"
    assert expression_for_state(RakoVisualState.SPEAKING) == "speaking"
    assert expression_for_state(RakoVisualState.USER_INACTIVE) == "sleepy"


def test_state_for_turn_phase_normalizes_common_names() -> None:
    assert state_for_turn_phase("waiting") is RakoVisualState.READY
    assert state_for_turn_phase("recording") is RakoVisualState.LISTENING
    assert state_for_turn_phase("whisper") is RakoVisualState.TRANSCRIBING
    assert state_for_turn_phase("rag") is RakoVisualState.THINKING
    assert state_for_turn_phase("playback") is RakoVisualState.SPEAKING
    assert state_for_turn_phase("pomodoro") is RakoVisualState.FOCUS_RUNNING


def test_visual_profiles_make_oled_states_product_friendly() -> None:
    listening = visual_profile_for_state(RakoVisualState.LISTENING)
    crisis = visual_profile_for_state(RakoVisualState.CRISIS)
    focus = visual_profile_for_state(RakoVisualState.FOCUS_RUNNING)

    assert listening.expression == "listening"
    assert listening.motion == "attentive"
    assert listening.brightness > focus.brightness
    assert crisis.motion == "steady"
    assert "crisis" in crisis.description
