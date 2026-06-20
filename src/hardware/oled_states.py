"""Map Rako runtime states to OLED eye expressions.

Pure mapping layer. The actual OLED renderer lives in `eyes.py` for now; runtime
code can call that script or import a future display service using these names.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

MotionStyle = Literal["calm", "attentive", "soft_pulse", "talking", "celebrate", "steady"]


class RakoVisualState(Enum):
    STARTING = "STARTING"
    READY = "READY"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    CAPTURED = "CAPTURED"
    TRANSCRIBING = "TRANSCRIBING"
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
    RakoVisualState.STARTING: "wink",
    RakoVisualState.READY: "neutral",
    RakoVisualState.IDLE: "neutral",
    RakoVisualState.LISTENING: "listening",
    RakoVisualState.CAPTURED: "surprised",
    RakoVisualState.TRANSCRIBING: "thinking",
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


@dataclass(frozen=True, slots=True)
class RakoVisualProfile:
    expression: str
    motion: MotionStyle
    brightness: float
    description: str


_PROFILE_BY_STATE: dict[RakoVisualState, RakoVisualProfile] = {
    RakoVisualState.STARTING: RakoVisualProfile("wink", "soft_pulse", 0.65, "saludo breve"),
    RakoVisualState.READY: RakoVisualProfile("neutral", "calm", 0.55, "disponible sin presionar"),
    RakoVisualState.IDLE: RakoVisualProfile("neutral", "calm", 0.45, "presencia tranquila"),
    RakoVisualState.LISTENING: RakoVisualProfile(
        "listening", "attentive", 0.85, "atención clara al usuario"
    ),
    RakoVisualState.CAPTURED: RakoVisualProfile(
        "surprised", "soft_pulse", 0.75, "confirmación de captura"
    ),
    RakoVisualState.TRANSCRIBING: RakoVisualProfile(
        "thinking", "soft_pulse", 0.65, "procesando audio"
    ),
    RakoVisualState.THINKING: RakoVisualProfile(
        "thinking", "soft_pulse", 0.65, "pensando sin ansiedad"
    ),
    RakoVisualState.SPEAKING: RakoVisualProfile("speaking", "talking", 0.8, "acompaña la voz"),
    RakoVisualState.FOCUS_RUNNING: RakoVisualProfile(
        "neutral", "steady", 0.5, "modo foco, baja distracción"
    ),
    RakoVisualState.FOCUS_DONE: RakoVisualProfile("happy", "celebrate", 0.85, "celebración breve"),
    RakoVisualState.USER_INACTIVE: RakoVisualProfile("sleepy", "calm", 0.35, "descanso visual"),
    RakoVisualState.HAPPY: RakoVisualProfile("happy", "celebrate", 0.85, "refuerzo positivo"),
    RakoVisualState.SAD: RakoVisualProfile("sad", "steady", 0.45, "acompañamiento sobrio"),
    RakoVisualState.CRISIS: RakoVisualProfile("sad", "steady", 0.55, "presencia estable en crisis"),
    RakoVisualState.ERROR: RakoVisualProfile(
        "surprised", "soft_pulse", 0.75, "algo requiere atención"
    ),
}


def expression_for_state(state: RakoVisualState) -> str:
    return _EXPRESSION_BY_STATE[state]


def visual_profile_for_state(state: RakoVisualState) -> RakoVisualProfile:
    return _PROFILE_BY_STATE[state]


def state_for_turn_phase(phase: str) -> RakoVisualState:
    normalized = phase.strip().lower()
    if normalized in {"starting", "boot", "startup"}:
        return RakoVisualState.STARTING
    if normalized in {"ready", "waiting", "button_wait"}:
        return RakoVisualState.READY
    if normalized in {"listening", "capture", "recording"}:
        return RakoVisualState.LISTENING
    if normalized in {"captured", "heard", "recorded"}:
        return RakoVisualState.CAPTURED
    if normalized in {"transcribing", "stt", "whisper"}:
        return RakoVisualState.TRANSCRIBING
    if normalized in {"thinking", "processing", "llm", "rag"}:
        return RakoVisualState.THINKING
    if normalized in {"speaking", "tts", "playback"}:
        return RakoVisualState.SPEAKING
    if normalized in {"focus", "pomodoro", "countdown"}:
        return RakoVisualState.FOCUS_RUNNING
    if normalized in {"idle", "sleep", "inactive"}:
        return RakoVisualState.USER_INACTIVE
    return RakoVisualState.IDLE
