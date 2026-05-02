"""Tests del indexer de ChromaDB."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chunker import parse_obsidian_note
from rag.indexer import IndexResult, index_chunks, index_vault
from rag.types import Chunk

_NOTE = """---
titulo: "Técnicas de respiración"
categoria: respiracion
tags: [#respiracion]
---

# Heading

## Qué es

Respira profundamente para reducir la ansiedad.

## Cómo se hace

Inhala 4 segundos, exhala 6 segundos.
"""


def _chunk(id: str = "x#0", text: str = "respira profundo", **meta: object) -> Chunk:
    return Chunk(id=id, text=text, metadata={"source": "x", **meta})


def test_index_chunks_returns_count(tmp_path: Path) -> None:
    chunks = (_chunk("a#0", "respira profundo"), _chunk("b#0", "grounding"))

    result = index_chunks(
        chunks=chunks,
        db_path=str(tmp_path / "chroma"),
        collection_name="test",
    )

    assert isinstance(result, IndexResult)
    assert result.indexed_count == 2


def test_index_is_idempotent(tmp_path: Path) -> None:
    chunks = (_chunk("a#0", "respira profundo"),)
    db_path = str(tmp_path / "chroma")

    r1 = index_chunks(chunks=chunks, db_path=db_path, collection_name="test")
    r2 = index_chunks(chunks=chunks, db_path=db_path, collection_name="test")

    # Idempotente: re-indexar no duplica.
    assert r1.indexed_count == 1
    assert r2.indexed_count == 1


def test_index_replaces_collection_on_each_run(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")

    index_chunks(
        chunks=(_chunk("old#0", "obsoleto"),),
        db_path=db_path,
        collection_name="test",
    )
    index_chunks(
        chunks=(_chunk("new#0", "nuevo"),),
        db_path=db_path,
        collection_name="test",
    )

    # Tras la segunda indexación, "obsoleto" ya no está.
    from rag.chroma_retriever import ChromaRetriever

    retriever = ChromaRetriever(db_path=db_path, collection_name="test")
    results = retriever.query("obsoleto")
    assert all(c.id != "old#0" for c in results)


def test_index_vault_walks_directory(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "01.md").write_text(_NOTE)

    result = index_vault(
        vault_path=str(vault),
        db_path=str(tmp_path / "chroma"),
        collection_name="test",
    )

    assert result.indexed_count >= 1


def test_index_vault_raises_on_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        index_vault(
            vault_path=str(tmp_path / "missing"),
            db_path=str(tmp_path / "chroma"),
            collection_name="test",
        )


def test_index_chunks_rejects_empty_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        index_chunks(
            chunks=(),
            db_path=str(tmp_path / "chroma"),
            collection_name="test",
        )


def test_chunked_note_round_trips_through_index_and_query(tmp_path: Path) -> None:
    parsed = parse_obsidian_note(_NOTE, source="01_tecnicas")
    from rag.chunker import chunk_note

    chunks = chunk_note(parsed)

    db_path = str(tmp_path / "chroma")
    index_chunks(chunks=chunks, db_path=db_path, collection_name="rako_kb")

    from rag.chroma_retriever import ChromaRetriever

    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")
    results = retriever.query("respira profundo", top_k=2)

    assert len(results) >= 1
    # El chunk recuperado debe pertenecer a la nota original.
    assert all(r.id.startswith("01_tecnicas#") for r in results)
