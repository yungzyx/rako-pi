"""RAG local sobre la vault de Obsidian.

ChromaDB persistente en disco con embeddings multiidioma. La fuente de
verdad del contenido es `../Rako-kb/`. La indexación se reconstruye con
`scripts/reindex_rag.py` cuando la vault cambia.

Recuperación: top-K=5 por defecto. Soporta filtros por metadata
(categoría, situación, duración) declarada en el front-matter de cada
nota Obsidian.

El RAG SIEMPRE funciona offline. Nunca depende de internet.
"""
