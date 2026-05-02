"""Re-indexa la vault de Obsidian en ChromaDB.

Uso:
    PYTHONPATH=src python scripts/reindex_rag.py

Lee `OBSIDIAN_VAULT_PATH`, `CHROMA_DB_PATH`, `CHROMA_COLLECTION` desde
`.env` (vía `Settings`) y reescribe la colección desde cero.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Añadir src al path para que el script sea ejecutable directo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import Settings
from rag.indexer import index_vault


def main() -> int:
    settings = Settings()
    result = index_vault(
        vault_path=settings.obsidian_vault_path,
        db_path=settings.chroma_db_path,
        collection_name=settings.chroma_collection,
    )
    print(
        f"Indexados {result.indexed_count} chunks en colección "
        f"'{result.collection_name}' desde {settings.obsidian_vault_path}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
