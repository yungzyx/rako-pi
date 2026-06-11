from __future__ import annotations

import pytest

from orchestrator.memory import ConversationMemory


def test_conversation_memory_keeps_recent_turns_only() -> None:
    memory = ConversationMemory(max_turns=2)

    memory.add_turn(user="primer turno", rako="respuesta uno")
    memory.add_turn(user="segundo turno", rako="respuesta dos")
    memory.add_turn(user="tercer turno", rako="respuesta tres")

    assert memory.lines() == (
        "Usuario: segundo turno",
        "Rako: respuesta dos",
        "Usuario: tercer turno",
        "Rako: respuesta tres",
    )


def test_conversation_memory_truncates_long_text() -> None:
    memory = ConversationMemory(max_turns=1)

    memory.add_turn(user="x" * 240, rako="ok")

    assert len(memory.lines()[0]) < 200
    assert memory.lines()[0].endswith("…")


def test_conversation_memory_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError):
        ConversationMemory(max_turns=0)
