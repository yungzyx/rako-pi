"""Respaldo local del estado del usuario.

La motivación es concreta: una microSD muerta significa perder todo el
historial local (tareas, ánimo, logros, memoria editable) porque por
diseño esos datos nunca salen de la Pi (CLAUDE.md §4.1). Este módulo crea
snapshots consistentes de la base SQLite en un directorio elegido por el
operador (idealmente un USB u otra tarjeta), con rotación.

Privacidad: el snapshot se genera con `VACUUM INTO` sobre la conexión ya
abierta con la clave de SQLCipher, así que la copia queda cifrada con la
MISMA clave que la base original. Un backup sin `SQLITE_ENCRYPTION_KEY`
solo puede existir en dev (fuera de dev el arranque exige cifrado). La
clave debe respaldarse aparte: sin ella el snapshot es irrecuperable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from db.connection import open_connection

BACKUP_PREFIX = "rako-db-"
BACKUP_SUFFIX = ".db"
DEFAULT_KEEP = 7


@dataclass(frozen=True, slots=True)
class BackupResult:
    backup_path: Path
    size_bytes: int
    pruned: tuple[str, ...]


def create_backup(
    *,
    sqlite_path: str,
    encryption_key: str | None,
    output_dir: Path,
    now: datetime,
    keep: int = DEFAULT_KEEP,
) -> BackupResult:
    """Crea un snapshot consistente de la base y rota los antiguos.

    `VACUUM INTO` produce una copia íntegra aunque la base esté en modo WAL
    y con otros procesos leyendo; no requiere detener los servicios.
    """
    if keep < 1:
        raise ValueError("keep must be >= 1")
    source = Path(sqlite_path)
    if not source.exists():
        raise FileNotFoundError(f"database not found: {source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    destination = output_dir / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
    if destination.exists():
        raise FileExistsError(f"backup already exists: {destination}")

    conn = open_connection(str(source), encryption_key)
    try:
        conn.execute("VACUUM INTO ?", (str(destination),))
    finally:
        conn.close()

    pruned = _prune_old_backups(output_dir, keep=keep)
    return BackupResult(
        backup_path=destination,
        size_bytes=destination.stat().st_size,
        pruned=pruned,
    )


def list_backups(output_dir: Path) -> tuple[Path, ...]:
    """Backups existentes, del más nuevo al más viejo (por nombre/fecha)."""
    if not output_dir.is_dir():
        return ()
    candidates = [
        path
        for path in output_dir.iterdir()
        if path.is_file()
        and path.name.startswith(BACKUP_PREFIX)
        and path.name.endswith(BACKUP_SUFFIX)
    ]
    return tuple(sorted(candidates, key=lambda path: path.name, reverse=True))


def _prune_old_backups(output_dir: Path, *, keep: int) -> tuple[str, ...]:
    backups = list_backups(output_dir)
    pruned: list[str] = []
    for stale in backups[keep:]:
        stale.unlink()
        pruned.append(stale.name)
    return tuple(pruned)
