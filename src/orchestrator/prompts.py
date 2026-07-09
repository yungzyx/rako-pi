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


# Guía de estilo + identidad. Va en el rol `system` (una vez, estable → se
# cachea), NO re-inyectada en cada mensaje del usuario. Reescrita en positivo y
# recortada: la versión anterior tenía 18 reglas "no hagas X" —incluidas frases
# malas citadas literal ("Veo que no tienes tareas…") que el modelo terminaba
# imitando (pink-elephant)— y dominaba la atención de un modelo chico como
# gpt-4o-mini, dejando el turno real sepultado al final.
RESPONSE_GUIDE = (
    "# Quién eres\n"
    "Eres Rako: un compañero de estudio para estudiantes universitarios chilenos. "
    "Tu dominio es estudio, organización, foco, descanso y pausas del día a día. No "
    "desarrolles temas clínicos ni de salud mental; si aparecen, deriva con calidez a la "
    "unidad de bienestar.\n\n"
    "# Cómo conversas\n"
    "- Habla natural y cálido, como alguien que acompaña en la mesa. Corto: 2 a 4 oraciones.\n"
    "- Continúa el hilo: retoma lo que venían hablando, sin volver a saludar ni reiniciar el tema.\n"
    "- Máximo una pregunta por turno, y no cierres siempre preguntando: a veces basta con "
    "proponer el siguiente paso y dejar espacio.\n"
    "- Cuando pidan ayuda con una tarea, divídela en pasos pequeños y concretos, y ofrece un "
    "primer paso accionable para ahora.\n"
    "- Usa el contexto agregado y la memoria del usuario solo si aporta; no los recites ni "
    "digas 'recuerdo que...'. Menciona tareas, nivel u hora solo si te preguntan o suma de verdad.\n"
    "- Sé cálido pero directo: una recomendación concreta vale más que motivación genérica."
)


def build_system_prompt(base_prompt: str) -> str:
    """Compone el system prompt: persona base (nota KB o fallback) + la guía de
    respuesta. Se manda UNA vez como rol `system` (prefijo estable, cacheable),
    en vez de re-inyectar las reglas en cada mensaje del usuario."""
    return f"{base_prompt.strip()}\n\n{RESPONSE_GUIDE}"


def format_user_context(ctx: UserContext) -> str:
    """Resumen agregado, anonimizado. El historial NO va acá: se manda como
    turnos reales user/assistant (ver `build_conversation_messages`)."""
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
    if ctx.support_hint:
        lines.append(f"Nota de tono para este turno: {ctx.support_hint}")
    return "\n".join(lines)


def build_user_message(
    query: str,
    chunks: Iterable[Chunk],
    context: UserContext,
) -> str:
    """Mensaje del turno ACTUAL: contexto agregado + material RAG + la consulta.

    La identidad y las reglas de estilo ya viven en el system prompt
    (`build_system_prompt`) y el historial va como turnos reales — acá solo va
    lo específico de este turno, con la consulta al final."""
    return (
        "## Contexto del usuario\n"
        f"{format_user_context(context)}\n\n"
        "## Material relevante (curado, no inventar)\n"
        f"{format_chunks_for_prompt(chunks)}\n\n"
        "## Turno actual del usuario\n"
        f"{query.strip()}"
    )


def build_conversation_messages(
    query: str,
    chunks: Iterable[Chunk],
    context: UserContext,
) -> list[dict[str, str]]:
    """Historial como turnos reales user/assistant + el turno actual al final.

    Los turnos previos vienen de `ConversationMemory` (ya truncados a 180 chars,
    §4.1.3) — pasarlos como ROLES reales, no como texto citado, es lo que hace
    que el modelo siga el hilo en vez de re-responder el primer turno. Mismo
    contenido que antes salía en viñetas; solo cambia la forma."""
    messages: list[dict[str, str]] = []
    for user_turn, rako_turn in context.conversation_turns:
        # Solo intercambios completos → alternancia estricta user/assistant
        # (Anthropic rechaza mensajes consecutivos del mismo rol). En la
        # práctica la respuesta de Rako nunca es vacía; esto es defensivo.
        if not (user_turn and rako_turn):
            continue
        messages.append({"role": "user", "content": user_turn})
        messages.append({"role": "assistant", "content": rako_turn})
    messages.append({"role": "user", "content": build_user_message(query, chunks, context)})
    return messages
