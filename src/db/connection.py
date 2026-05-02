"""Conexión a SQLite (con SQLCipher en producción).

En desarrollo (mac, Python 3.12) usamos `sqlite3` de stdlib porque los
wheels de SQLCipher no están disponibles. En la Pi, `db/encryption.py`
intercepta `open_connection` para usar `pysqlcipher3` y aplicar
`PRAGMA key`. Los repositorios son agnósticos.

Antes de aceptar tráfico productivo, llamar a `require_encrypted` —
aborta si la base no está cifrada.
"""

from __future__ import annotations

import sqlite3
from typing import Final

from db import encryption


class EncryptionRequiredError(RuntimeError):
    """La base no está cifrada y la operación lo exige."""


_PRAGMAS: Final[tuple[str, ...]] = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
)


def open_connection(path: str, key: str | None = None) -> sqlite3.Connection:
    """Abre una conexión a SQLite. Si `key` es no vacío, intenta cifrado.

    Devuelve una conexión con `sqlite3.Row` como factory de filas y los
    pragmas de seguridad activados.
    """
    conn = encryption.open_encrypted(path, key) if key else sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    return conn


def require_encrypted(conn: sqlite3.Connection) -> None:
    """Aborta si `conn` no está cifrada. Llamar antes de aceptar tráfico."""
    if not encryption.is_encrypted(conn):
        raise EncryptionRequiredError(
            "Database is not encrypted. Refusing to accept traffic. "
            "Provision SQLCipher (pysqlcipher3 + libsqlcipher-dev) and "
            "restart with SQLITE_ENCRYPTION_KEY set."
        )
