#!/usr/bin/env python3
"""CLI de respaldo local del estado de Rako.

Crea un snapshot cifrado de la base SQLite (misma clave SQLCipher que la
original) en el directorio indicado y rota los antiguos. Pensado para un
USB montado o un cron diario — una microSD muerta no debe borrar la
historia del usuario.

Uso:
    ./scripts/rako-backup                          # ./backups, conserva 7
    ./scripts/rako-backup --output-dir /media/usb/rako --keep 14
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from config import Settings
from product.backup import DEFAULT_KEEP, create_backup, list_backups


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respaldar la base local de Rako")
    parser.add_argument(
        "--output-dir",
        default="backups",
        help="Directorio destino de los snapshots (default: ./backups)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"Cantidad de snapshots a conservar (default: {DEFAULT_KEEP})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Solo listar los backups existentes, sin crear uno nuevo",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    if args.list:
        backups = list_backups(output_dir)
        if not backups:
            print(f"No hay backups en {output_dir}.")
            return 0
        for path in backups:
            print(f"{path.name}  ({path.stat().st_size} bytes)")
        return 0

    settings = Settings()
    result = create_backup(
        sqlite_path=settings.sqlite_path,
        encryption_key=settings.sqlite_encryption_key,
        output_dir=output_dir,
        now=datetime.now(UTC),
        keep=args.keep,
    )
    print(f"Backup creado: {result.backup_path} ({result.size_bytes} bytes)")
    if result.pruned:
        print(f"Rotados: {', '.join(result.pruned)}")
    if not settings.sqlite_encryption_key:
        print("AVISO: la base no tiene SQLITE_ENCRYPTION_KEY (dev). Este backup NO está cifrado.")
    else:
        print(
            "El backup queda cifrado con la misma SQLITE_ENCRYPTION_KEY. "
            "Respalda esa clave aparte: sin ella el snapshot es irrecuperable."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
