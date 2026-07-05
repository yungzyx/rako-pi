"""Smoke test: indexar y querear la base de conocimiento real (`knowledge-base/`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chroma_retriever import ChromaRetriever
from rag.indexer import index_vault

_VAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge-base"


@pytest.mark.skipif(not _VAULT_PATH.exists(), reason="Rako-kb vault not checked out")
def test_real_vault_indexes_and_queries(tmp_path: Path) -> None:
    db_path = str(tmp_path / "chroma")
    result = index_vault(
        vault_path=str(_VAULT_PATH),
        db_path=db_path,
        collection_name="rako_kb",
    )

    notes = [p for p in _VAULT_PATH.glob("*.md") if not p.name.startswith(".")]
    assert result.indexed_count >= len(notes)  # al menos un chunk por nota

    retriever = ChromaRetriever(db_path=db_path, collection_name="rako_kb")
    results = retriever.query("postergación y evasión", top_k=5)

    assert len(results) >= 1
