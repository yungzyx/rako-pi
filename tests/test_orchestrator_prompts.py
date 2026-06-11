"""Tests del cargador del system prompt y el constructor de mensajes."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.prompts import (
    build_user_message,
    extract_system_prompt,
    format_chunks_for_prompt,
    format_user_context,
)
from orchestrator.types import UserContext
from rag.types import Chunk

_FAKE_KB_NOTE = """---
titulo: "System Prompt Base — Rako"
---

# System Prompt Base — Rako

> Doc explicativo.

## Prompt (copiar directamente al sistema)

```
# ROL
Eres Rako: un asistente de acompañamiento emocional.

# PRINCIPIOS
Sé breve. Valida antes de sugerir.
```

## Notas adicionales

Texto que NO va al prompt.
"""


def test_extract_system_prompt_pulls_first_fenced_block() -> None:
    extracted = extract_system_prompt(_FAKE_KB_NOTE)

    assert "Eres Rako" in extracted
    assert "Sé breve" in extracted
    assert "Notas adicionales" not in extracted
    assert "# ROL" in extracted


def test_extract_system_prompt_raises_when_no_fenced_block() -> None:
    with pytest.raises(ValueError):
        extract_system_prompt("# Title\n\nNo fenced block here.")


def test_extract_system_prompt_from_real_kb_path(tmp_path: Path) -> None:
    file = tmp_path / "system_prompt_rako.md"
    file.write_text(_FAKE_KB_NOTE)

    extracted = extract_system_prompt(file.read_text())

    assert "Eres Rako" in extracted


def test_format_chunks_includes_id_and_text() -> None:
    chunks = (
        Chunk(id="01_tecnicas#0", text="Respira profundo.", metadata={"categoria": "respiracion"}),
        Chunk(id="02_grounding#0", text="5-4-3-2-1.", metadata={"categoria": "grounding"}),
    )

    formatted = format_chunks_for_prompt(chunks)

    assert "01_tecnicas#0" in formatted
    assert "Respira profundo" in formatted
    assert "5-4-3-2-1" in formatted


def test_format_chunks_returns_empty_marker_when_no_chunks() -> None:
    formatted = format_chunks_for_prompt(())

    assert "sin material" in formatted.lower() or "no hay" in formatted.lower()


def test_format_user_context_omits_pii_and_includes_safe_aggregates() -> None:
    ctx = UserContext(
        pending_task_count=4,
        recent_completion_count=2,
        robot_level=3,
        time_of_day="noche",
        recent_mood_summary="cansado pero abierto a conversar",
    )

    formatted = format_user_context(ctx)

    assert "4" in formatted
    assert "noche" in formatted
    assert "cansado" in formatted
    # Privacidad: ningún nombre, ningún ID, ningún vector crudo.
    assert "nombre" not in formatted.lower()
    assert "valencia" not in formatted.lower()


def test_format_user_context_includes_recent_conversation_when_present() -> None:
    ctx = UserContext(
        pending_task_count=1,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        recent_conversation=("Usuario: quiero estudiar", "Rako: Dale, partimos."),
    )

    formatted = format_user_context(ctx)

    assert "Conversación reciente" in formatted
    assert "quiero estudiar" in formatted
    assert "Dale, partimos" in formatted


def test_build_user_message_combines_query_chunks_and_context() -> None:
    chunks = (Chunk(id="01#0", text="Respira profundo.", metadata={}),)
    ctx = UserContext(
        pending_task_count=2,
        recent_completion_count=1,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
    )

    message = build_user_message(query="Me siento atascado", chunks=chunks, context=ctx)

    assert "Me siento atascado" in message
    assert "Respira profundo" in message
    assert "tarde" in message


def test_build_user_message_tells_llm_to_continue_existing_topic() -> None:
    ctx = UserContext(
        pending_task_count=1,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        recent_conversation=("Usuario: ayúdame con cálculo", "Rako: Partamos por límites."),
    )

    message = build_user_message(query="ya, sigamos", chunks=(), context=ctx)

    assert "continúa algo" in message
    assert "sin volver a saludar" in message
    assert "Partamos por límites" in message


def test_build_user_message_guides_task_breakdowns_and_suggestions() -> None:
    ctx = UserContext(
        pending_task_count=3,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
    )

    message = build_user_message(
        query="No sé cómo empezar el informe",
        chunks=(),
        context=ctx,
    )

    lowered = message.lower()
    assert "divide" in lowered
    assert "pasos pequeños" in lowered
    assert "sugerencia" in lowered
    assert "asistente académico" in lowered
    assert "salud mental" in lowered


def test_build_user_message_handles_empty_chunks() -> None:
    ctx = UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=0,
        time_of_day="mañana",
        recent_mood_summary=None,
    )

    message = build_user_message(query="hola", chunks=(), context=ctx)

    assert "hola" in message


def test_build_user_message_does_not_leak_metadata_secrets() -> None:
    chunks = (Chunk(id="01#0", text="x", metadata={"source_path": "/private/path/file.md"}),)
    ctx = UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=0,
        time_of_day="día",
        recent_mood_summary=None,
    )

    message = build_user_message(query="hola", chunks=chunks, context=ctx)

    assert "/private/path" not in message
