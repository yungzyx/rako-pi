"""Comandos de memoria editable por WhatsApp: recordar, listar, olvidar.

Regla de privacidad (CLAUDE.md §4.1): las memorias `sensitivity=sensitive`
NUNCA salen por este canal — solo se informa su cantidad.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from channels.whatsapp.results import WhatsAppInboundResult
from product.user_config import UserConfigService

if TYPE_CHECKING:
    from channels.whatsapp.service import WhatsAppService

_REMEMBER_PREFIXES = ("rako recuerda que ", "recuerda que ", "rako recuerda ", "recuerda ")
_FORGET_PREFIXES = ("rako olvida que ", "olvida que ", "rako olvida ", "olvida ")
_LIST_TRIGGERS = frozenset(
    {"memoria", "mis recuerdos", "que sabes de mi", "qué sabes de mí", "qué sabes de mi"}
)
_MAX_LISTED_MEMORIES = 5


def handle_memory_command(
    service: WhatsAppService, text: str, *, from_number: str
) -> WhatsAppInboundResult | None:
    normalized = text.lower().strip()
    config = UserConfigService(service._db)
    remember_prefix = _matching_prefix(normalized, _REMEMBER_PREFIXES)
    if remember_prefix is not None:
        return _remember(service, config, text, prefix=remember_prefix, from_number=from_number)
    if normalized in _LIST_TRIGGERS:
        return _list_memories(service, config, from_number=from_number)
    forget_prefix = _matching_prefix(normalized, _FORGET_PREFIXES)
    if forget_prefix is not None:
        return _forget(service, config, text, prefix=forget_prefix, from_number=from_number)
    return None


def _matching_prefix(normalized: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return prefix
    return None


def _remember(
    service: WhatsAppService,
    config: UserConfigService,
    text: str,
    *,
    prefix: str,
    from_number: str,
) -> WhatsAppInboundResult:
    original_text = text[len(prefix) :].strip()
    if not original_text:
        return service._reply(
            to=from_number,
            action="MEMORY_HELP",
            response_text="Dime algo concreto, por ejemplo: recuerda que prefiero bloques de 25 minutos.",
        )
    memory = config.add_memory(text=original_text, category="preference")
    return service._reply(
        to=from_number,
        action="MEMORY_ADDED",
        response_text=f"Listo, lo guardé: {memory.text}",
    )


def _list_memories(
    service: WhatsAppService, config: UserConfigService, *, from_number: str
) -> WhatsAppInboundResult:
    all_memories = config.list_memory()
    if not all_memories:
        return service._reply(
            to=from_number,
            action="MEMORY_LIST",
            response_text="Todavía no tengo recuerdos guardados sobre tus preferencias.",
        )
    # Las memorias sensibles nunca salen por este canal — el mismo filtro
    # que ya aplica el contexto del LLM (orchestrator/context.py).
    normal_memories = [m for m in all_memories if m.sensitivity == "normal"]
    sensitive_count = len(all_memories) - len(normal_memories)
    sensitive_note = (
        f"(Tienes {sensitive_count} recuerdo(s) sensible(s) guardado(s); revísalos en la app.)"
    )
    if not normal_memories:
        return service._reply(to=from_number, action="MEMORY_LIST", response_text=sensitive_note)
    lines = [f"- {memory.text}" for memory in normal_memories[:_MAX_LISTED_MEMORIES]]
    if sensitive_count:
        lines.append(sensitive_note)
    return service._reply(
        to=from_number,
        action="MEMORY_LIST",
        response_text="Esto tengo guardado:\n" + "\n".join(lines),
    )


def _forget(
    service: WhatsAppService,
    config: UserConfigService,
    text: str,
    *,
    prefix: str,
    from_number: str,
) -> WhatsAppInboundResult:
    query = text[len(prefix) :].strip()
    if not query:
        return service._reply(
            to=from_number,
            action="MEMORY_DELETE_HELP",
            response_text="Dime qué recuerdo borrar, por ejemplo: olvida bloques de 25 minutos.",
        )
    if _delete_memory_matching(config, query):
        return service._reply(
            to=from_number,
            action="MEMORY_DELETED",
            response_text="Listo, borré ese recuerdo.",
        )
    return service._reply(
        to=from_number,
        action="MEMORY_NOT_FOUND",
        response_text="No encontré un recuerdo que coincida con eso.",
    )


def _delete_memory_matching(config: UserConfigService, query: str) -> bool:
    clean_query = query.strip().lower()
    if not clean_query:
        return False
    for memory in config.list_memory():
        if clean_query in memory.text.lower():
            return config.delete_memory(memory.id)
    return False
