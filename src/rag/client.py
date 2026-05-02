"""Retriever Protocol y `InMemoryRetriever` para tests / fallback offline.

`Retriever` es la interfaz que consume el orquestador — `query(text,
top_k, where)` devuelve chunks ordenados por relevancia. La
implementación concreta sobre ChromaDB se enchufa en `rag/embeddings.py`
(siguiente ciclo). Mientras tanto, `InMemoryRetriever` permite probar
el resto del sistema con un retriever determinístico.

`InMemoryRetriever` también es un fallback razonable cuando ChromaDB no
está disponible (Pi sin provisionar) — busca por overlap de tokens, sin
embeddings.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any, Protocol, runtime_checkable

from rag.types import Chunk


@runtime_checkable
class Retriever(Protocol):
    def query(
        self,
        text: str,
        top_k: int = 5,
        where: Mapping[str, Any] | None = None,
    ) -> tuple[Chunk, ...]: ...


class InMemoryRetriever:
    """Retriever naive por overlap de tokens. Sin embeddings."""

    def __init__(self, chunks: Iterable[Chunk]) -> None:
        self._chunks = tuple(chunks)

    def query(
        self,
        text: str,
        top_k: int = 5,
        where: Mapping[str, Any] | None = None,
    ) -> tuple[Chunk, ...]:
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")
        normalized_query = _normalize(text)
        if not normalized_query:
            raise ValueError("query text is empty")

        terms = set(normalized_query.split())
        ranked: list[tuple[int, Chunk]] = []
        for chunk in self._chunks:
            if where and not _matches_filter(chunk.metadata, where):
                continue
            chunk_text = _normalize(chunk.text)
            score = sum(1 for t in terms if t in chunk_text)
            if score > 0:
                ranked.append((score, chunk))

        ranked.sort(key=lambda item: -item[0])
        return tuple(chunk for _, chunk in ranked[:top_k])


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    text = text.lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


def _matches_filter(metadata: Mapping[str, Any], where: Mapping[str, Any]) -> bool:
    return all(metadata.get(k) == v for k, v in where.items())
