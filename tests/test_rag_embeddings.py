"""Tests del wrapper de embedding functions."""

from __future__ import annotations

import pytest

from rag.embeddings import (
    DefaultEmbeddingFunction,
    EmbeddingFunction,
    build_embedder,
)


def test_default_satisfies_protocol() -> None:
    fn: EmbeddingFunction = DefaultEmbeddingFunction()

    assert callable(fn)


def test_default_returns_vectors_for_each_text() -> None:
    fn = DefaultEmbeddingFunction()

    vectors = fn(["respira profundo", "técnica de grounding"])

    assert len(vectors) == 2
    assert all(len(v) > 0 for v in vectors)
    assert all(isinstance(x, float) for v in vectors for x in v)


def test_default_produces_consistent_dimensionality() -> None:
    fn = DefaultEmbeddingFunction()

    a = fn(["x"])
    b = fn(["y"])

    assert len(a[0]) == len(b[0])


def test_default_rejects_empty_input() -> None:
    fn = DefaultEmbeddingFunction()

    with pytest.raises(ValueError):
        fn([])


def test_build_embedder_returns_none_without_model() -> None:
    # Sin nombre de modelo, el pipeline debe caer a la default de ChromaDB.
    assert build_embedder(None) is None
    assert build_embedder("") is None
