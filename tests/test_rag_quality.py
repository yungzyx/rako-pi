"""Evals de calidad del RAG — queries doradas contra una vault fixture.

Los tests unitarios del RAG verifican mecánica (chunkeo, indexado); estos
verifican RELEVANCIA: que consultas típicas de un estudiante recuperen la
nota correcta. La vault fixture imita el estilo de contenido curado de
Rako-kb sin depender de que la vault real esté clonada.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chroma_retriever import ChromaRetriever
from rag.indexer import index_vault

_FIXTURE_VAULT = Path(__file__).resolve().parent / "fixtures" / "rag_vault"

_GOLDEN_QUERIES: tuple[tuple[str, str], ...] = (
    ("no puedo respirar bien antes de la prueba, ando muy ansioso", "respiracion"),
    ("quiero hacer un pomodoro de 25 minutos para estudiar", "pomodoro"),
    ("llevo días postergando el informe y me siento pésimo", "procrastinacion"),
    ("estoy trasnochando mucho estudiando y duermo poco", "sueno"),
)


@pytest.fixture(scope="module")
def retriever(tmp_path_factory: pytest.TempPathFactory) -> ChromaRetriever:
    db_path = str(tmp_path_factory.mktemp("chroma-eval"))
    result = index_vault(
        vault_path=str(_FIXTURE_VAULT),
        db_path=db_path,
        collection_name="rako_eval",
    )
    assert result.indexed_count >= len(_GOLDEN_QUERIES)
    return ChromaRetriever(db_path=db_path, collection_name="rako_eval")


@pytest.mark.parametrize(("query", "expected_source"), _GOLDEN_QUERIES)
def test_golden_query_retrieves_expected_note(
    retriever: ChromaRetriever, query: str, expected_source: str
) -> None:
    results = retriever.query(query, top_k=2)

    assert results, f"sin resultados para: {query}"
    sources = [str(chunk.metadata.get("source")) for chunk in results]
    assert expected_source in sources, (
        f"query {query!r} recuperó {sources}, se esperaba {expected_source}"
    )


def test_top_result_is_the_expected_note_for_most_queries(
    retriever: ChromaRetriever,
) -> None:
    # Métrica agregada: el top-1 debe acertar en al menos 3 de 4 queries.
    # Más laxa que el test por-query (top-2) a propósito: mide precisión
    # fina sin volver el gate frágil ante cambios menores de embedding.
    hits = 0
    for query, expected_source in _GOLDEN_QUERIES:
        results = retriever.query(query, top_k=1)
        if results and results[0].metadata.get("source") == expected_source:
            hits += 1
    assert hits >= 3, f"top-1 acertó solo {hits}/4 queries doradas"
