"""Migraciones versionadas del esquema local (PRAGMA user_version).

`schema.create_all` sigue siendo el DDL base idempotente para bases
nuevas. Este módulo cubre el caso que `CREATE TABLE IF NOT EXISTS` no
cubre: un dispositivo con datos reales que hace `git pull` de una versión
con cambios de esquema (columnas nuevas, índices, backfills).

Reglas:
- Cada cambio de esquema posterior al baseline se agrega como una
  `Migration` numerada, contigua y APPEND-ONLY (nunca editar una
  migración ya publicada — los dispositivos ya la aplicaron).
- `apply_migrations(conn)` lleva la base desde su `user_version` actual
  hasta `SCHEMA_VERSION`, una transacción por migración.
- Si la base declara una versión MAYOR que el código, se aborta: correr
  código viejo sobre un esquema nuevo puede corromper datos.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    description: str
    statements: tuple[str, ...]


# El baseline (v1) es el esquema completo que aplica `schema.create_all`;
# no lleva statements porque create_all ya corrió — solo estampa versión.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="baseline: esquema completo de schema.create_all",
        statements=(),
    ),
)

SCHEMA_VERSION = MIGRATIONS[-1].version


class SchemaTooNewError(RuntimeError):
    """La base fue creada por código más nuevo que este binario."""


def get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def apply_migrations(conn: sqlite3.Connection) -> tuple[int, ...]:
    """Aplica las migraciones pendientes en orden. Devuelve las versiones
    aplicadas en esta corrida (vacío si la base ya estaba al día)."""
    current = get_schema_version(conn)
    if current > SCHEMA_VERSION:
        raise SchemaTooNewError(
            f"database schema is version {current} but this code supports up to "
            f"{SCHEMA_VERSION}. Update the code (git pull) before opening this database."
        )

    applied: list[int] = []
    for migration in MIGRATIONS:
        if migration.version <= current:
            continue
        with conn:
            for statement in migration.statements:
                conn.execute(statement)
            # PRAGMA no acepta parámetros; version viene de código, no de input.
            conn.execute(f"PRAGMA user_version = {int(migration.version)}")
        applied.append(migration.version)
    return tuple(applied)


def _validate_migrations() -> None:
    versions = [migration.version for migration in MIGRATIONS]
    expected = list(range(1, len(MIGRATIONS) + 1))
    if versions != expected:
        raise AssertionError(f"MIGRATIONS must be contiguous starting at 1, got {versions}")


_validate_migrations()
