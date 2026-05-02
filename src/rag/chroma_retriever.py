"""ChromaRetriever — implementación real de `Retriever` sobre ChromaDB.

Reemplaza a `InMemoryRetriever` cuando hay un índice persistido. Si la
colección no existe (no se ha re-indexado), retorna vacío sin levantar
— preferimos degradar suavemente a fallar duro.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import chromadb

from rag.types import Chunk


class ChromaRetriever:
    def __init__(self, db_path: str, collection_name: str) -> None:
        self._db_path = db_path
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(path=db_path)

    def query(
        self,
        text: str,
        top_k: int = 5,
        where: Mapping[str, Any] | None = None,
    ) -> tuple[Chunk, ...]:
        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}")
        if not text.strip():
            raise ValueError("query text is empty")

        try:
            collection = self._client.get_collection(name=self._collection_name)
        except Exception:
            return ()

        result = collection.query(
            query_texts=[text],
            n_results=top_k,
            where=dict(where) if where else None,
        )
        return tuple(_unpack_results(result))


def _unpack_results(result: Mapping[str, Any]) -> list[Chunk]:
    ids = result.get("ids") or [[]]
    documents = result.get("documents") or [[]]
    metadatas = result.get("metadatas") or [[]]
    if not ids or not ids[0]:
        return []

    chunks: list[Chunk] = []
    for chunk_id, text, metadata in zip(ids[0], documents[0], metadatas[0], strict=False):
        chunks.append(
            Chunk(
                id=chunk_id,
                text=text or "",
                metadata=dict(metadata) if metadata else {},
            )
        )
    return chunks
