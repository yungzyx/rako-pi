"""Configuración global de pytest.

El marker `hardware` se registra en `pyproject.toml`. Este archivo
expone fixtures compartidos.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from db.connection import open_connection
from db.schema import create_all


@pytest.fixture
def db_conn() -> Iterator:
    """Conexión SQLite :memory: con esquema aplicado."""
    conn = open_connection(":memory:")
    create_all(conn)
    try:
        yield conn
    finally:
        conn.close()
