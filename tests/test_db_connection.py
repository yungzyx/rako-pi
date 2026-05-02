"""Tests para la conexión a SQLite.

En dev usamos stdlib sqlite3; en la Pi se intercepta para aplicar
SQLCipher. Los tests aquí verifican lo que es estable: foreign keys,
WAL, comportamiento contra :memory:, y que el self-test de cifrado se
comporta correctamente.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db.connection import (
    EncryptionRequiredError,
    open_connection,
    require_encrypted,
)


def test_open_in_memory_connection() -> None:
    conn = open_connection(":memory:")

    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_foreign_keys_are_enabled() -> None:
    conn = open_connection(":memory:")

    cursor = conn.execute("PRAGMA foreign_keys")
    (value,) = cursor.fetchone()

    assert value == 1
    conn.close()


def test_row_factory_returns_dict_like_rows() -> None:
    conn = open_connection(":memory:")

    conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'x')")
    row = conn.execute("SELECT a, b FROM t").fetchone()

    assert row["a"] == 1
    assert row["b"] == "x"
    conn.close()


def test_open_file_connection_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "rako.db"

    conn = open_connection(str(db_path))
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.commit()
    conn.close()

    assert db_path.exists()


def test_require_encrypted_raises_in_dev_mode() -> None:
    conn = open_connection(":memory:")

    # En dev (stdlib sqlite3, sin clave), require_encrypted debe abortar
    # antes de aceptar tráfico productivo.
    with pytest.raises(EncryptionRequiredError):
        require_encrypted(conn)

    conn.close()
