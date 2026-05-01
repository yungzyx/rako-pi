"""Script para re-indexar la vault de Obsidian en ChromaDB.

Uso:
    python scripts/reindex_rag.py

Lee `OBSIDIAN_VAULT_PATH` desde el .env, llama a `src.rag.indexer` y
deja la colección lista para queries.
"""
