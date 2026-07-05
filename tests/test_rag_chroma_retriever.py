"""Tests del ChromaRetriever (Retriever sobre ChromaDB persistente)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chroma_retriever import ChromaRetriever
from rag.client import Retriever
from rag.indexer import index_chunks
from rag.types import Chunk


def _seed(db_path: str) -> None:
    chunks = (
        Chunk(
            id="01#0",
            text="Respira profundamente para reducir la ansiedad aguda.",
            metadata={"source": "01_tecnicas", "categoria": "respiracion"},
        ),
        Chunk(
            id="02#0",
            text="Grounding sensorial: 5 cosas que ves, 4 que escuchas.",
            metadata={"source": "02_grounding", "categoria": "grounding"},
        ),
        Chunk(
            id="03#0",
            text="Postergación crónica y patrones de evasión post-trauma.",
            metadata={"source": "12_patrones", "categoria": "patrones"},
        ),
    )
    index_chunks(chunks=chunks, db_path=db_path, collection_name="rako_kb")


def test_satisfies_retriever_protocol(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    _seed(db_path)

    retriever: Retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")

    assert hasattr(retriever, "query")


def test_query_returns_chunks_ordered_by_similarity(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    _seed(db_path)
    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")

    results = retriever.query("respiración para ansiedad", top_k=3)

    assert len(results) >= 1
    # El primer resultado debería ser el chunk de respiración.
    assert results[0].id == "01#0"


def test_query_respects_top_k(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    _seed(db_path)
    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")

    results = retriever.query("técnica", top_k=2)

    assert len(results) <= 2


def test_query_filters_by_metadata(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    _seed(db_path)
    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")

    results = retriever.query(
        "técnica",
        top_k=5,
        where={"categoria": "grounding"},
    )

    assert all(c.metadata.get("categoria") == "grounding" for c in results)


def test_query_rejects_empty_text(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    _seed(db_path)
    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")

    with pytest.raises(ValueError):
        retriever.query("   ")


def test_query_rejects_non_positive_top_k(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    _seed(db_path)
    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")

    for bad in (0, -1):
        with pytest.raises(ValueError):
            retriever.query("x", top_k=bad)


def test_query_with_filter_matching_nothing_returns_empty(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    _seed(db_path)
    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")

    results = retriever.query(
        "técnica",
        top_k=5,
        where={"categoria": "no-existe-jamás"},
    )

    assert results == ()


def test_query_handles_collection_missing(tmp_path: Path) -> None:
    # Si la colección no existe (no se indexó), query devuelve vacío.
    retriever = ChromaRetriever(db_path=str(tmp_path / "chroma"), collection_name="never-indexed")

    results = retriever.query("cualquier cosa")

    assert results == ()


class _FakeEmbedder:
    """Embedder determinístico por conteo de palabras clave (para tests)."""

    _VOCAB = ("foco", "sueno", "ansiedad")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(t.lower().count(w)) for w in self._VOCAB] for t in texts]


def test_query_uses_injected_embedder(tmp_path: Path) -> None:
    # Con un embedder inyectado, index y query calculan vectores con él y
    # ChromaDB solo los almacena/busca (el mismo embedder en ambos lados).
    embedder = _FakeEmbedder()
    db_path = str(tmp_path / "chroma")
    index_chunks(
        (
            Chunk(id="foco#0", text="foco foco foco", metadata={"source": "foco"}),
            Chunk(id="sueno#0", text="sueno sueno", metadata={"source": "sueno"}),
        ),
        db_path=db_path,
        collection_name="test_embedder",
        embedder=embedder,
    )
    retriever = ChromaRetriever(
        db_path=db_path, collection_name="test_embedder", embedder=embedder
    )

    results = retriever.query("foco", top_k=1)

    assert len(results) == 1
    assert results[0].metadata["source"] == "foco"
