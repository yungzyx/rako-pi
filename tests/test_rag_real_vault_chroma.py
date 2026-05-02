"""Smoke test: indexar y querear la vault real (`../Rako-kb`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chroma_retriever import ChromaRetriever
from rag.indexer import index_vault

_VAULT_PATH = Path(__file__).resolve().parents[2] / "Rako-kb"


@pytest.mark.skipif(not _VAULT_PATH.exists(), reason="Rako-kb vault not checked out")
def test_real_vault_indexes_and_queries(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    result = index_vault(
        vault_path=str(_VAULT_PATH),
        db_path=db_path,
        collection_name="rako_kb",
    )

    assert result.indexed_count > 100  # 144 chunks confirmados anteriormente

    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")
    results = retriever.query("postergación y evasión", top_k=5)

    assert len(results) >= 1
