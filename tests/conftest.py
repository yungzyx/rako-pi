"""Configuración global de pytest.

Registra el marker `hardware` para tests que requieren GPIO real, y
expone fixtures compartidos (mocks de hardware, fakes de cliente LLM,
ChromaDB temporal, SQLite en memoria).
"""
