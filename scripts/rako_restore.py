#!/usr/bin/env python3
"""CLI de restauración de un snapshot de rako-backup.

Valida el snapshot con la clave actual, aparta la base vigente como copia
pre-restore y deja el snapshot en su lugar. Detener los servicios antes:

    sudo systemctl stop rako-chat rako-api
    ./scripts/rako-restore backups/rako-db-20260704-040000.db
    sudo systemctl start rako-chat rako-api

Sin argumentos usa el snapshot más reciente de ./backups.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from config import Settings
from product.backup import list_backups, restore_backup


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restaurar un snapshot de la base de Rako")
    parser.add_argument(
        "backup",
        nargs="?",
        help="Ruta del snapshot; sin argumento usa el más reciente de --backups-dir",
    )
    parser.add_argument(
        "--backups-dir",
        default="backups",
        help="Directorio donde buscar el snapshot más reciente (default: ./backups)",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    if args.backup:
        backup_path = Path(args.backup)
    else:
        candidates = list_backups(Path(args.backups_dir))
        if not candidates:
            print(f"No hay snapshots en {args.backups_dir}.")
            return 1
        backup_path = candidates[0]
        print(f"Usando el snapshot más reciente: {backup_path.name}")

    print("Recuerda detener los servicios antes de restaurar (systemctl stop rako-chat rako-api).")
    result = restore_backup(
        backup_path=backup_path,
        sqlite_path=settings.sqlite_path,
        encryption_key=settings.sqlite_encryption_key,
        now=datetime.now(UTC),
    )
    print(f"Restaurado desde: {result.restored_from}")
    if result.pre_restore_copy is not None:
        print(f"La base anterior quedó en: {result.pre_restore_copy}")
    print("Listo. Reinicia los servicios y verifica con ./scripts/rako-doctor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
