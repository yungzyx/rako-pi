"""Short-lived conversational memory for one running Rako session.

This memory is intentionally process-local. It helps the LLM avoid sounding as
if every button press were the first turn, without persisting private chat text.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

_MAX_TEXT_LEN = 180


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


def _clean(text: str) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= _MAX_TEXT_LEN:
        return clean
    return clean[: _MAX_TEXT_LEN - 1].rstrip() + "…"
