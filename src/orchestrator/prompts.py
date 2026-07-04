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
        parts.append(f'<chunk id="{chunk.id}"{meta_str}>\n{chunk.text}\n</chunk>')
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
    if ctx.user_memory:
        lines.append("Memoria editable del usuario (usar solo si ayuda):")
        lines.extend(f"- {line}" for line in ctx.user_memory[-8:])
    if ctx.recent_conversation:
        lines.append("Conversación reciente de esta sesión:")
        lines.extend(f"- {line}" for line in ctx.recent_conversation[-8:])
    if ctx.support_hint:
        lines.append(f"Nota de tono para este turno: {ctx.support_hint}")
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
        "## Identidad de Rako\n"
        "- Eres Rako: asistente académico para estudiantes universitarios chilenos.\n"
        "- Tu dominio es estudio, organización, foco, descanso cotidiano y pausas.\n"
        "- No desarrolles temas clínicos ni de salud mental; si aparecen, deriva a recursos UDD.\n\n"
        "## Guía de respuesta\n"
        "- Responde corto por defecto: 2 a 4 oraciones.\n"
        "- Máximo una pregunta por turno.\n"
        "- Suena conversacional, como alguien que acompaña en la mesa: natural, directo y sin frases de plantilla.\n"
        "- No repitas estructuras como 'Veo que no tienes tareas pendientes' o '¿Hay algo específico...?'. Usa el contexto solo si aporta.\n"
        "- No menciones tareas pendientes, logros, hora del día o nivel del robot salvo que el usuario pregunte o sea claramente útil.\n"
        "- Usa la memoria editable para adaptar tono y sugerencias, pero no la cites literalmente ni digas 'recuerdo que...' salvo que el usuario lo pida.\n"
        "- Usa la conversación reciente para mantener continuidad, pero no la repitas ni la resumas salvo que ayude.\n"
        "- Si el usuario continúa algo que ya venían hablando, responde como continuación natural, sin volver a saludar ni reiniciar el tema.\n"
        "- Evita cerrar siempre con una pregunta. A veces basta con proponer el siguiente paso y dejar espacio.\n"
        "- Si el usuario pide ayuda con una tarea, divide la tarea en pasos pequeños y concretos.\n"
        "- Si el usuario ya va a estudiar, no lo llenes de técnicas: déjalo arrancar con un primer paso.\n"
        "- Si el usuario pide iniciar un conteo, temporizador, pomodoro o foco, interpreta la actividad concreta (por ejemplo estudiar, leer papers, programar, repasar cálculo) y no repitas la frase literal del usuario.\n"
        "- Nunca uses títulos incompletos como 'conteo de 30 minutos de', 'un conteo de' o 'para:'. Si falta actividad, di solo la duración.\n"
        "- Da una sugerencia accionable para empezar ahora, evitando listas largas.\n"
        "- Reconoce logros pequeños sin exagerar.\n"
        "- Sé cálido pero directivo: una recomendación concreta vale más que motivación genérica.\n"
        "- Si falta información importante, pregunta solo una cosa antes de avanzar.\n\n"
        "## Material relevante (curado, no inventar)\n"
        f"{format_chunks_for_prompt(chunks)}\n\n"
        "## Turno actual del usuario\n"
        f"{query.strip()}"
    )
