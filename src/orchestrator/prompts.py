"""Construcción de prompts para Claude.

- `extract_system_prompt(text)` lee el system prompt curado desde la nota
  Obsidian `system_prompt_rako.md`. El contenido real vive en el primer
  bloque fenced (```) del markdown.
- `format_chunks_for_prompt(chunks)` serializa los chunks RAG.
- `format_user_context(ctx)` rinde un resumen anonimizado del contexto.
- `build_user_message(query, chunks, ctx)` ensambla el mensaje del turno.

Privacidad: el LLM nunca recibe nombres reales, IDs, audio, o vector
emocional crudo. Solo recibe agregados (cantidades, hora del día,
resúmenes ya curados).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from orchestrator.types import UserContext
from rag.types import Chunk

_FENCED_RE: Final = re.compile(r"```(?:\w+)?\s*\n(.*?)\n```", re.DOTALL)


def extract_system_prompt(markdown_text: str) -> str:
    """Devuelve el contenido del primer bloque fenced en el markdown.

    Levanta `ValueError` si no hay bloque fenced — la nota debe tener
    el prompt entre triple-backtick.
    """
    match = _FENCED_RE.search(markdown_text)
    if match is None:
        raise ValueError("system prompt note does not contain a fenced block")
    return match.group(1).strip()


def format_chunks_for_prompt(chunks: Iterable[Chunk]) -> str:
    """Serializa los chunks RAG para inyectar al LLM."""
    chunks_list = list(chunks)
    if not chunks_list:
        return "No hay material relevante en este turno."
    parts: list[str] = []
    for chunk in chunks_list:
        meta_bits = []
        for key in ("section", "categoria", "tipo"):
            value = chunk.metadata.get(key)
            if value:
                meta_bits.append(f"{key}={value}")
        meta_str = f" [{', '.join(meta_bits)}]" if meta_bits else ""
        parts.append(f"<chunk id=\"{chunk.id}\"{meta_str}>\n{chunk.text}\n</chunk>")
    return "\n\n".join(parts)


def format_user_context(ctx: UserContext) -> str:
    """Resumen agregado, anonimizado."""
    lines = [
        f"Hora del día: {ctx.time_of_day}.",
        f"Tareas pendientes: {ctx.pending_task_count}.",
        f"Tareas completadas recientemente: {ctx.recent_completion_count}.",
        f"Nivel del robot: {ctx.robot_level}.",
    ]
    if ctx.recent_mood_summary:
        lines.append(f"Sensación reciente: {ctx.recent_mood_summary}.")
    return "\n".join(lines)


def build_user_message(
    query: str,
    chunks: Iterable[Chunk],
    context: UserContext,
) -> str:
    """Ensambla el mensaje del turno."""
    return (
        "## Contexto del usuario\n"
        f"{format_user_context(context)}\n\n"
        "## Material relevante (curado, no inventar)\n"
        f"{format_chunks_for_prompt(chunks)}\n\n"
        "## Turno actual del usuario\n"
        f"{query.strip()}"
    )
