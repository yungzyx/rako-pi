"""Tipos compartidos del módulo RAG."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ParsedNote:
    """Una nota Obsidian parseada en frontmatter + body."""

    source: str
    frontmatter: Mapping[str, Any] = field(default_factory=dict)
    body: str = ""


@dataclass(frozen=True, slots=True)
class Chunk:
    """Fragmento indexable: texto + metadata para filtros del retriever."""

    id: str
    text: str
    metadata: Mapping[str, Any]
