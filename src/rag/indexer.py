"""Pipeline de indexación de la vault Obsidian en ChromaDB.

Idempotente: cada llamada a `index_chunks` o `index_vault` borra la
colección y la reescribe. Es lo correcto para una vault que es la
fuente de verdad — los chunks borrados de la vault deben desaparecer
del índice.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from rag.chunker import chunk_vault
from rag.embeddings import Embedder
from rag.types import Chunk


@dataclass(frozen=True, slots=True)
class IndexResult:
    indexed_count: int
    collection_name: str


def index_chunks(
    chunks: Iterable[Chunk],
    db_path: str,
    collection_name: str,
    embedder: Embedder | None = None,
) -> IndexResult:
    """Indexa una iterable de chunks en una colección de ChromaDB.

    Si se pasa `embedder`, los vectores se calculan con él (multilingüe) y
    ChromaDB solo los almacena; el retriever debe usar el mismo embedder. Si es
    `None`, ChromaDB usa su embedding function default.
    """
    chunks_list = list(chunks)
    if not chunks_list:
        raise ValueError("cannot index an empty chunk list")

    client = chromadb.PersistentClient(path=db_path)
    # Borrar y recrear es más simple y seguro que upsertear: la vault
    # siempre es la fuente de verdad. delete_collection levanta si la
    # colección no existe — lo suprimimos.
    with contextlib.suppress(Exception):
        client.delete_collection(name=collection_name)
    collection = client.create_collection(name=collection_name)

    add_kwargs: dict[str, Any] = {
        "ids": [c.id for c in chunks_list],
        "documents": [c.text for c in chunks_list],
        "metadatas": [dict(c.metadata) for c in chunks_list],
    }
    if embedder is not None:
        add_kwargs["embeddings"] = embedder.embed([c.text for c in chunks_list])
    collection.add(**add_kwargs)
    return IndexResult(indexed_count=len(chunks_list), collection_name=collection_name)


def index_vault(
    vault_path: str,
    db_path: str,
    collection_name: str,
    embedder: Embedder | None = None,
) -> IndexResult:
    """Camina la vault, chunkea, e indexa."""
    if not Path(vault_path).exists():
        raise FileNotFoundError(f"vault path not found: {vault_path}")
    return index_chunks(
        chunks=chunk_vault(Path(vault_path)),
        db_path=db_path,
        collection_name=collection_name,
        embedder=embedder,
    )
