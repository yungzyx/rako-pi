"""Pipeline de indexación de la vault de Obsidian.

Lee los .md de `OBSIDIAN_VAULT_PATH`, parsea el front-matter, hace
chunking respetando secciones, calcula embeddings y reescribe la
colección de ChromaDB. Idempotente: borra y rehace.
"""
