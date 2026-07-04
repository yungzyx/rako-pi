"""Short-lived conversational memory for one running Rako session.

This memory is intentionally process-local. It helps the LLM avoid sounding as
if every button press were the first turn, without persisting private chat text.

También vive acá la detección de respuestas repetidas: comparar lo que el
LLM acaba de generar contra lo que Rako ya dijo en la sesión, para poder
pedirle una reformulación en vez de sonar a disco rayado.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher

_MAX_TEXT_LEN = 180

_RAKO_LINE_PREFIX = "Rako: "
# Umbral de similitud (SequenceMatcher) sobre texto normalizado a partir
# del cual dos respuestas se consideran "la misma cosa dicha de nuevo".
_REPEAT_SIMILARITY_THRESHOLD = 0.82
# Líneas muy cortas ("ok", "dale") matchean entre sí sin ser repetición
# real — solo comparamos respuestas con algo de sustancia.
_MIN_COMPARABLE_LEN = 20


@dataclass(slots=True)
class ConversationMemory:
    max_turns: int = 4
    _turns: deque[tuple[str, str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_turns <= 0:
            raise ValueError(f"max_turns must be positive, got {self.max_turns}")
        self._turns = deque(maxlen=self.max_turns)

    def add_turn(self, *, user: str, rako: str) -> None:
        user_clean = _clean(user)
        rako_clean = _clean(rako)
        if not user_clean and not rako_clean:
            return
        self._turns.append((user_clean, rako_clean))

    def lines(self) -> tuple[str, ...]:
        lines: list[str] = []
        for user, rako in self._turns:
            if user:
                lines.append(f"Usuario: {user}")
            if rako:
                lines.append(f"Rako: {rako}")
        return tuple(lines)

    def clear(self) -> None:
        self._turns.clear()


def is_near_repeat(candidate: str, recent_lines: tuple[str, ...]) -> bool:
    """True si `candidate` es casi idéntico a algo que Rako ya dijo.

    `recent_lines` es el formato de `ConversationMemory.lines()` — solo se
    comparan las líneas "Rako: ...". Como las líneas guardadas vienen
    truncadas a 180 caracteres, la comparación usa el prefijo equivalente
    del candidato.
    """
    normalized_candidate = _normalize_for_comparison(candidate)
    if len(normalized_candidate) < _MIN_COMPARABLE_LEN:
        return False
    for line in recent_lines:
        if not line.startswith(_RAKO_LINE_PREFIX):
            continue
        stored = _normalize_for_comparison(line[len(_RAKO_LINE_PREFIX) :].rstrip("…"))
        if len(stored) < _MIN_COMPARABLE_LEN:
            continue
        trimmed = normalized_candidate[: len(stored)]
        ratio = SequenceMatcher(None, trimmed, stored).ratio()
        if ratio >= _REPEAT_SIMILARITY_THRESHOLD:
            return True
    return False


def _normalize_for_comparison(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def _clean(text: str) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= _MAX_TEXT_LEN:
        return clean
    return clean[: _MAX_TEXT_LEN - 1].rstrip() + "…"
