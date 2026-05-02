"""Boundary de cifrado para la base local.

Producción usa `pysqlcipher3` con la clave en `SQLITE_ENCRYPTION_KEY`.
En dev (mac/Python 3.12) los wheels no están disponibles, así que el
boundary funciona pero `is_encrypted` retorna False y `require_encrypted`
aborta.

Convención de clave: hex de 32 bytes mínimo (`openssl rand -hex 32`).
Se aplica a SQLCipher como literal `x'<hex>'`, no como passphrase. Esto
evita ambigüedad de codificación, derivación PBKDF2 innecesaria, y
elimina el riesgo de que la clave aparezca en tracebacks de SQL.

Cuando se aprovisione la Pi:
    sudo apt install libsqlcipher-dev sqlcipher
    pip install pysqlcipher3
"""

from __future__ import annotations

import re
import sqlite3
from typing import Final

try:  # pragma: no cover - rama dependiente del entorno
    from pysqlcipher3 import dbapi2 as _sqlcipher  # type: ignore[import-not-found]

    _SQLCIPHER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _sqlcipher = None
    _SQLCIPHER_AVAILABLE = False


_HEX_KEY_RE: Final = re.compile(r"^[0-9a-fA-F]+$")
_MIN_HEX_KEY_LEN: Final = 32  # 16 bytes mínimo (recomendado: 64 = 32 bytes)


class KeyFormatError(ValueError):
    """La clave de cifrado no cumple el formato hex requerido."""


def validate_key_format(key: str) -> None:
    """Valida que `key` sea hex de longitud par y >= 16 bytes.

    Se llama antes de `open_encrypted`. Levanta `KeyFormatError` con un
    mensaje que NO incluye el contenido de la clave.
    """
    if not key:
        raise KeyFormatError("encryption key is empty")
    if len(key) < _MIN_HEX_KEY_LEN:
        raise KeyFormatError(f"encryption key too short: need >= {_MIN_HEX_KEY_LEN} hex chars")
    if len(key) % 2 != 0:
        raise KeyFormatError("encryption key must have even length (hex bytes)")
    if not _HEX_KEY_RE.match(key):
        raise KeyFormatError("encryption key must be hex (0-9, a-f, A-F only)")


def open_encrypted(path: str, key: str) -> sqlite3.Connection:
    """Abre una conexión cifrada y aplica la clave como literal hex.

    Si SQLCipher no está disponible, lanza `RuntimeError` — preferimos
    fallar antes que abrir una base sin cifrado pretendiendo cifrarla.
    """
    validate_key_format(key)

    if not _SQLCIPHER_AVAILABLE:  # pragma: no cover - solo en prod sin libs
        raise RuntimeError("SQLCipher not available. Install pysqlcipher3 + libsqlcipher-dev.")

    conn = _sqlcipher.connect(path)  # pragma: no cover
    # Literal hex `x'<hex>'`: SQLCipher trata estos 32 bytes como la
    # clave directa (sin derivación). No requiere escaping y no expone
    # el valor en tracebacks de manera reconstructible.
    conn.execute(f"PRAGMA key = \"x'{key}'\"")  # pragma: no cover
    return conn  # pragma: no cover


def is_encrypted(conn: sqlite3.Connection) -> bool:
    """True si la conexión usa SQLCipher con clave aplicada."""
    if not _SQLCIPHER_AVAILABLE:
        return False
    return isinstance(conn, _sqlcipher.Connection)  # pragma: no cover
