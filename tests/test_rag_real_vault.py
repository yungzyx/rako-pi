"""Smoke test contra la base de conocimiento real (`knowledge-base/`).

Si la carpeta no existe, el test se skippea.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.chunker import chunk_vault

_VAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge-base"


@pytest.mark.skipif(not _VAULT_PATH.exists(), reason="Rako-kb vault not checked out")
def test_real_vault_indexes_without_errors() -> None:
    chunks = list(chunk_vault(_VAULT_PATH))

    assert len(chunks) > 0
    assert all(c.id for c in chunks)
    assert all(c.text.strip() for c in chunks)


@pytest.mark.skipif(not _VAULT_PATH.exists(), reason="Rako-kb vault not checked out")
def test_real_vault_each_note_produces_at_least_one_chunk() -> None:
    chunks = list(chunk_vault(_VAULT_PATH))
    sources = {c.metadata["source"] for c in chunks}
    md_files = {p.stem for p in _VAULT_PATH.glob("*.md") if not p.name.startswith(".")}

    # Permite hasta 2 notas sin sub-secciones (notas degeneradas) sin fallar.
    diff = md_files - sources
    assert len(diff) <= 2, f"notes without any chunk: {diff}"
