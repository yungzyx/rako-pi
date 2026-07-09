"""Tests del cargador del system prompt y el constructor de mensajes."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.prompts import (
    build_conversation_messages,
    build_system_prompt,
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


def test_recent_conversation_goes_as_real_turns_not_context_text() -> None:
    # El historial ya NO va como texto citado en el contexto del usuario: se
    # manda como turnos reales user/assistant (así el modelo sigue el hilo).
    ctx = UserContext(
        pending_task_count=1,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        conversation_turns=(("quiero estudiar", "Dale, partimos."),),
    )

    formatted = format_user_context(ctx)
    assert "Dale, partimos" not in formatted  # no como texto de contexto

    messages = build_conversation_messages("sigamos", (), ctx)
    assert messages[0] == {"role": "user", "content": "quiero estudiar"}
    assert messages[1] == {"role": "assistant", "content": "Dale, partimos."}
    assert messages[-1]["role"] == "user"
    assert "sigamos" in messages[-1]["content"]


def test_format_user_context_includes_editable_memory_when_present() -> None:
    ctx = UserContext(
        pending_task_count=1,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        user_memory=("routine: Prefiere bloques de 25 minutos",),
    )

    formatted = format_user_context(ctx)

    assert "Memoria editable" in formatted
    assert "Prefiere bloques de 25 minutos" in formatted


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


def test_system_prompt_tells_llm_to_continue_thread() -> None:
    system = build_system_prompt("Eres Rako.")

    assert "Eres Rako." in system  # persona base preservada
    assert "Continúa el hilo" in system
    assert "sin volver a saludar" in system


def test_conversation_messages_keep_strict_user_assistant_alternation() -> None:
    # Un par incompleto (respuesta vacía) se descarta para no romper la
    # alternancia estricta que exige la API de Anthropic.
    ctx = UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        conversation_turns=(("hola", "qué tal"), ("a medias", "")),
    )

    messages = build_conversation_messages("sigue", (), ctx)

    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "user"]  # el par incompleto se omite
    for a, b in zip(roles, roles[1:], strict=False):
        assert a != b  # nunca dos mensajes seguidos del mismo rol


def test_prior_turn_is_carried_as_assistant_message() -> None:
    ctx = UserContext(
        pending_task_count=1,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        conversation_turns=(("ayúdame con cálculo", "Partamos por límites."),),
    )

    messages = build_conversation_messages("ya, sigamos", (), ctx)

    assert {"role": "assistant", "content": "Partamos por límites."} in messages
    # La consulta actual queda al final, como último turno de usuario.
    assert messages[-1]["role"] == "user"
    assert "ya, sigamos" in messages[-1]["content"]


def test_build_user_message_includes_editable_memory_but_guidance_is_in_system() -> None:
    ctx = UserContext(
        pending_task_count=1,
        recent_completion_count=0,
        robot_level=1,
        time_of_day="tarde",
        recent_mood_summary=None,
        user_memory=("motivation: Le sirven instrucciones directas y cortas",),
    )

    message = build_user_message(query="ayúdame a partir", chunks=(), context=ctx)

    # El DATO agregado (memoria editable) va en el turno; la REGLA de no
    # recitarla vive en el system prompt, no re-inyectada cada turno.
    assert "memoria editable" in message.lower()
    assert "no los recites" in build_system_prompt("x").lower()


def test_system_prompt_carries_identity_and_response_guidance() -> None:
    system = build_system_prompt("Base persona.")
    lowered = system.lower()

    assert "Base persona." in system
    assert "compañero de estudio" in lowered
    assert "salud mental" in lowered  # frontera clínica
    assert "pasos pequeños" in lowered
    assert "primer paso" in lowered


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
