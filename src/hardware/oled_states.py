"""Map Rako runtime states to OLED eye expressions.

Pure mapping layer. The actual OLED renderer lives in `eyes.py` for now; runtime
code can call that script or import a future display service using these names.
"""

from __future__ import annotations

from enum import Enum


class RakoVisualState(Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    FOCUS_RUNNING = "FOCUS_RUNNING"
    FOCUS_DONE = "FOCUS_DONE"
    USER_INACTIVE = "USER_INACTIVE"
    HAPPY = "HAPPY"
    SAD = "SAD"
    CRISIS = "CRISIS"
    ERROR = "ERROR"


_EXPRESSION_BY_STATE: dict[RakoVisualState, str] = {
    RakoVisualState.IDLE: "neutral",
    RakoVisualState.LISTENING: "listening",
    RakoVisualState.THINKING: "thinking",
    RakoVisualState.SPEAKING: "speaking",
    RakoVisualState.FOCUS_RUNNING: "neutral",
    RakoVisualState.FOCUS_DONE: "happy",
    RakoVisualState.USER_INACTIVE: "sleepy",
    RakoVisualState.HAPPY: "happy",
    RakoVisualState.SAD: "sad",
    RakoVisualState.CRISIS: "sad",
    RakoVisualState.ERROR: "surprised",
}


def expression_for_state(state: RakoVisualState) -> str:
    return _EXPRESSION_BY_STATE[state]


def state_for_turn_phase(phase: str) -> RakoVisualState:
    normalized = phase.strip().lower()
    if normalized in {"listening", "capture", "recording"}:
        return RakoVisualState.LISTENING
    if normalized in {"thinking", "processing", "llm", "rag"}:
        return RakoVisualState.THINKING
    if normalized in {"speaking", "tts", "playback"}:
        return RakoVisualState.SPEAKING
    if normalized in {"focus", "pomodoro", "countdown"}:
        return RakoVisualState.FOCUS_RUNNING
    if normalized in {"idle", "sleep", "inactive"}:
        return RakoVisualState.USER_INACTIVE
    return RakoVisualState.IDLE
