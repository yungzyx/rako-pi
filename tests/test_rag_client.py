"""Tests del Retriever Protocol y el InMemoryRetriever (fallback offline)."""

from __future__ import annotations

import pytest

from rag.client import InMemoryRetriever, Retriever
from rag.types import Chunk


def _chunk(id: str, text: str, **metadata: object) -> Chunk:
    return Chunk(id=id, text=text, metadata={"source": id.split("#")[0], **metadata})


def test_retriever_protocol_is_satisfied_by_inmemory() -> None:
    retriever: Retriever = InMemoryRetriever([])

    assert hasattr(retriever, "query")


def test_query_returns_chunks_ranked_by_term_overlap() -> None:
    chunks = [
        _chunk("a#0", "respiración profunda para reducir ansiedad"),
        _chunk("b#0", "técnica de grounding sensorial"),
        _chunk("c#0", "respiración profunda y mindfulness"),
    ]
    retriever = InMemoryRetriever(chunks)

    result = retriever.query("respiración ansiedad")

    ids = [c.id for c in result]
    assert ids[0] == "a#0"
    assert "c#0" in ids


def test_query_respects_top_k() -> None:
    chunks = [_chunk(f"{i}#0", f"texto x{i} relevante") for i in range(10)]
    retriever = InMemoryRetriever(chunks)

    result = retriever.query("relevante", top_k=3)

    assert len(result) == 3


def test_query_filters_by_metadata() -> None:
    chunks = [
        _chunk("a#0", "respiración profunda", categoria="respiracion"),
        _chunk("b#0", "respiración profunda", categoria="grounding"),
    ]
    retriever = InMemoryRetriever(chunks)

    result = retriever.query("respiración", where={"categoria": "respiracion"})

    assert len(result) == 1
    assert result[0].id == "a#0"


def test_query_with_no_matches_returns_empty() -> None:
    chunks = [_chunk("a#0", "respiración profunda")]
    retriever = InMemoryRetriever(chunks)

    result = retriever.query("xyz123")

    assert result == ()


def test_query_is_case_insensitive_and_accent_insensitive() -> None:
    chunks = [_chunk("a#0", "técnicas de respiración")]
    retriever = InMemoryRetriever(chunks)

    result = retriever.query("RESPIRACION")

    assert len(result) == 1


def test_query_rejects_non_positive_top_k() -> None:
    retriever = InMemoryRetriever([])

    for bad in (0, -1):
        with pytest.raises(ValueError):
            retriever.query("x", top_k=bad)


def test_query_rejects_empty_text() -> None:
    retriever = InMemoryRetriever([_chunk("a#0", "x")])

    with pytest.raises(ValueError):
        retriever.query("   ")


def test_metadata_filter_with_missing_key_excludes_chunk() -> None:
    chunks = [
        _chunk("a#0", "x", categoria="respiracion"),
        _chunk("b#0", "x"),  # sin categoría
    ]
    retriever = InMemoryRetriever(chunks)

    result = retriever.query("x", where={"categoria": "respiracion"})

    assert {c.id for c in result} == {"a#0"}
