"""Boundary de cifrado para la base local.

Producción usa `pysqlcipher3` con la clave en `SQLITE_ENCRYPTION_KEY`.
En dev (mac/Python 3.12) los wheels no están disponibles, así que el
boundary funciona pero `is_encrypted` retorna False y `require_encrypted`
aborta.

Cuando se aprovisione la Pi:
    sudo apt install libsqlcipher-dev sqlcipher
    pip install pysqlcipher3

y este módulo carga `pysqlcipher3.dbapi2` automáticamente.
"""

from __future__ import annotations

import sqlite3

try:  # pragma: no cover - rama dependiente del entorno
    from pysqlcipher3 import dbapi2 as _sqlcipher  # type: ignore[import-not-found]

    _SQLCIPHER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _sqlcipher = None
    _SQLCIPHER_AVAILABLE = False


def open_encrypted(path: str, key: str) -> sqlite3.Connection:
    """Abre una conexión cifrada y aplica `PRAGMA key`.

    Si SQLCipher no está disponible, lanza `RuntimeError` — preferimos
    fallar antes que abrir una base sin cifrado pretendiendo cifrarla.
    """
    if not _SQLCIPHER_AVAILABLE:  # pragma: no cover - solo en prod sin libs
        raise RuntimeError(
            "SQLCipher not available. Install pysqlcipher3 + libsqlcipher-dev."
        )

    conn = _sqlcipher.connect(path)  # pragma: no cover
    conn.execute(f"PRAGMA key = '{_escape(key)}'")  # pragma: no cover
    return conn  # pragma: no cover


def is_encrypted(conn: sqlite3.Connection) -> bool:
    """True si la conexión usa SQLCipher con clave aplicada."""
    if not _SQLCIPHER_AVAILABLE:
        return False
    return isinstance(conn, _sqlcipher.Connection)  # pragma: no cover


def _escape(key: str) -> str:
    # Escape de comilla simple para `PRAGMA key`. La clave nunca se
    # loggea ni se imprime fuera de aquí.
    return key.replace("'", "''")
