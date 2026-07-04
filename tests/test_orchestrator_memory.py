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


# ---------------------------------------------------------------------------
# Detección de repetición (is_near_repeat)
# ---------------------------------------------------------------------------


def test_near_repeat_detects_identical_rako_line() -> None:
    from orchestrator.memory import is_near_repeat

    lines = ("Usuario: hola", "Rako: Partamos con un bloque corto de 25 minutos de cálculo.")

    assert is_near_repeat("Partamos con un bloque corto de 25 minutos de cálculo.", lines) is True


def test_near_repeat_detects_trivially_reworded_line() -> None:
    from orchestrator.memory import is_near_repeat

    lines = ("Rako: Partamos con un bloque corto de 25 minutos de cálculo.",)

    assert is_near_repeat("partamos con un bloque corto de 25 minutos de calculo", lines) is True


def test_different_response_is_not_a_repeat() -> None:
    from orchestrator.memory import is_near_repeat

    lines = ("Rako: Partamos con un bloque corto de 25 minutos de cálculo.",)

    assert (
        is_near_repeat("¿Y si primero anotas las tres dudas principales del capítulo?", lines)
        is False
    )


def test_short_lines_never_count_as_repeats() -> None:
    from orchestrator.memory import is_near_repeat

    lines = ("Rako: Dale.",)

    assert is_near_repeat("Dale.", lines) is False


def test_user_lines_are_ignored_for_repetition() -> None:
    from orchestrator.memory import is_near_repeat

    lines = ("Usuario: quiero estudiar cálculo con un bloque de 25 minutos",)

    assert is_near_repeat("quiero estudiar cálculo con un bloque de 25 minutos", lines) is False


def test_truncated_stored_line_still_matches_by_prefix() -> None:
    from orchestrator.memory import ConversationMemory, is_near_repeat

    memory = ConversationMemory()
    long_reply = "Vamos paso a paso con el informe de laboratorio: " + "detalle " * 30
    memory.add_turn(user="ayúdame con el informe", rako=long_reply)

    assert is_near_repeat(long_reply, memory.lines()) is True
