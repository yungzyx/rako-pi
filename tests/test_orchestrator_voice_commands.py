"""Tests del parser de comandos de voz locales (sin LLM)."""

from __future__ import annotations

import pytest

from orchestrator.voice_commands import parse_remember_command


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("recuerda que prefiero estudiar de noche", "prefiero estudiar de noche"),
        ("Rako recuerda que me gustan los bloques de 25", "me gustan los bloques de 25"),
        ("rako recuerda tomar agua en las pausas", "tomar agua en las pausas"),
        ("Recuerda que los viernes no estudio", "los viernes no estudio"),
    ],
)
def test_remember_command_extracts_memory_text(transcript: str, expected: str) -> None:
    assert parse_remember_command(transcript) == expected


@pytest.mark.parametrize(
    "transcript",
    [
        "quiero estudiar cálculo",
        "me recuerda a mi infancia",  # "recuerda" en medio de frase no es comando
        "recuerda que",  # sin contenido
        "recuerda   ",
        "",
    ],
)
def test_non_commands_return_none(transcript: str) -> None:
    assert parse_remember_command(transcript) is None


def test_command_preserves_original_casing_of_memory_text() -> None:
    assert (
        parse_remember_command("recuerda que los Lunes tengo Cálculo II")
        == "los Lunes tengo Cálculo II"
    )


def test_synonym_prefixes_parse_like_recuerda() -> None:
    assert parse_remember_command("acuérdate de que odio madrugar") == "odio madrugar"
    assert parse_remember_command("acuerdate de que odio madrugar") == "odio madrugar"
    assert (
        parse_remember_command("no te olvides de que estudio mejor de noche")
        == "estudio mejor de noche"
    )
    assert parse_remember_command("no olvides que mi ramo difícil es cálculo") == (
        "mi ramo difícil es cálculo"
    )
    assert parse_remember_command("Rako acuérdate de que uso bloques de 25") == (
        "uso bloques de 25"
    )


def test_bare_synonyms_are_not_commands() -> None:
    assert parse_remember_command("acuérdate de que") is None
    assert parse_remember_command("no olvides que") is None
