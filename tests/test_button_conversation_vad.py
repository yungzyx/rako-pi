"""Tests for the button conversation end-of-turn VAD helper."""

from __future__ import annotations

import importlib.util
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "button_conversation.py"
_spec = importlib.util.spec_from_file_location("button_conversation", _SCRIPT)
assert _spec is not None and _spec.loader is not None
button_conversation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(button_conversation)


def _pcm16(values: list[int]) -> bytes:
    return struct.pack("<" + "h" * len(values), *values)


@dataclass
class _FakeOrchestrator:
    kind: object
    calls: int = 0

    def handle_turn(self, turn):
        self.calls += 1
        return SimpleNamespace(kind=self.kind, text="respuesta curada")


def test_guardrail_result_catches_exact_reported_ideation_phrase() -> None:
    app = SimpleNamespace(
        orchestrator=_FakeOrchestrator(button_conversation.TurnKind.CRISIS_PROTOCOL)
    )

    result = button_conversation._guardrail_result_for_transcript(
        app=app,
        transcript="Me quiero matar.",
        now=datetime(2026, 5, 14, 22, 58, tzinfo=UTC),
    )

    assert result is not None
    assert result.kind is button_conversation.TurnKind.CRISIS_PROTOCOL
    assert app.orchestrator.calls == 1


def test_guardrail_result_takes_priority_over_local_intents() -> None:
    app = SimpleNamespace(
        orchestrator=_FakeOrchestrator(button_conversation.TurnKind.CRISIS_PROTOCOL)
    )

    result = button_conversation._guardrail_result_for_transcript(
        app=app,
        transcript="quiero desaparecer",
        now=datetime(2026, 5, 14, 19, 58, tzinfo=UTC),
    )

    assert result is not None
    assert result.kind is button_conversation.TurnKind.CRISIS_PROTOCOL
    assert app.orchestrator.calls == 1


def test_guardrail_result_ignores_normal_llm_turns_for_local_intents() -> None:
    app = SimpleNamespace(orchestrator=_FakeOrchestrator(button_conversation.TurnKind.LLM_RESPONSE))

    result = button_conversation._guardrail_result_for_transcript(
        app=app,
        transcript="Rako, voy a estudiar cálculo 30 minutos",
        now=datetime(2026, 5, 14, 19, 58, tzinfo=UTC),
    )

    assert result is None
    assert app.orchestrator.calls == 0


def test_trim_after_end_of_turn_keeps_speech_plus_required_silence() -> None:
    sample_rate = 10
    # 1s silence, 1s speech, 3s trailing silence. Threshold sees only the speech block.
    data = _pcm16([0] * 10 + [1000] * 10 + [0] * 30)

    trimmed = button_conversation._trim_after_end_of_turn_pcm16(
        data,
        sample_rate=sample_rate,
        end_silence_seconds=1.5,
        threshold=100,
        frame_ms=100,
    )

    assert len(trimmed) == (10 + 10 + 15) * 2


def test_trim_after_end_of_turn_never_cuts_inside_late_speech() -> None:
    sample_rate = 10
    # Speech appears again near the end; keep through that speech plus available tail.
    data = _pcm16([0] * 10 + [1000] * 10 + [0] * 10 + [900] * 10 + [0] * 5)

    trimmed = button_conversation._trim_after_end_of_turn_pcm16(
        data,
        sample_rate=sample_rate,
        end_silence_seconds=1.5,
        threshold=100,
        frame_ms=100,
    )

    assert trimmed == data


def test_trim_after_end_of_turn_returns_original_when_no_voice_detected() -> None:
    data = _pcm16([0] * 50)

    trimmed = button_conversation._trim_after_end_of_turn_pcm16(
        data,
        sample_rate=10,
        end_silence_seconds=1.5,
        threshold=100,
        frame_ms=100,
    )

    assert trimmed == data
