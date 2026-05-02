"""Detector de palabra de activación.

`SubstringWakeWordDetector` opera sobre TEXTO (post-STT o input
sintético en tests). Para detección continua sobre audio, este detector
se enchufa después de un STT en streaming.

Producción: considerar Picovoice Porcupine u openWakeWord (modelos
entrenados, lower CPU). Este detector es el fallback dev/CI.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WakeWordHit:
    phrase: str


class WakeWordDetector(Protocol):
    def detect(self, text: str) -> WakeWordHit | None: ...


class SubstringWakeWordDetector:
    def __init__(self, phrases: Iterable[str]) -> None:
        normalized = tuple(_normalize(p) for p in phrases)
        if not normalized:
            raise ValueError("at least one wake-word phrase is required")
        if any(not p for p in normalized):
            raise ValueError("wake-word phrases must be non-empty")
        self._phrases = normalized

    def detect(self, text: str) -> WakeWordHit | None:
        normalized = _normalize(text)
        if not normalized:
            return None
        for phrase in self._phrases:
            if _contains_word_boundary(normalized, phrase):
                return WakeWordHit(phrase=phrase)
        return None


def _normalize(text: str) -> str:
    text = text.lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


def _contains_word_boundary(haystack: str, needle: str) -> bool:
    pattern = rf"\b{re.escape(needle)}\b"
    return re.search(pattern, haystack) is not None
