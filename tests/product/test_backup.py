"""Tests del respaldo local de la base SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from db.database import Database
from product.backup import BackupResult, create_backup, list_backups


def _now(minute: int = 0) -> datetime:
    return datetime(2026, 7, 4, 12, minute, 0, tzinfo=UTC)


def _seed_database(tmp_path: Path) -> str:
    sqlite_path = str(tmp_path / "rako.db")
    db = Database.open(sqlite_path, None)
    db.config.set("preferred_name", "Nico")
    db.close()
    return sqlite_path


def test_create_backup_produces_consistent_snapshot(tmp_path: Path) -> None:
    sqlite_path = _seed_database(tmp_path)
    output_dir = tmp_path / "backups"

    result = create_backup(
        sqlite_path=sqlite_path,
        encryption_key=None,
        output_dir=output_dir,
        now=_now(),
    )

    assert isinstance(result, BackupResult)
    assert result.backup_path.exists()
    assert result.size_bytes > 0
    assert result.pruned == ()
    # El snapshot es una base completa y legible por sí misma.
    conn = sqlite3.connect(result.backup_path)
    try:
        row = conn.execute("SELECT value FROM user_config WHERE key = 'preferred_name'").fetchone()
    finally:
        conn.close()
    assert row is not None
    assert "Nico" in row[0]


def test_create_backup_rotates_old_snapshots(tmp_path: Path) -> None:
    sqlite_path = _seed_database(tmp_path)
    output_dir = tmp_path / "backups"

    for minute in range(4):
        result = create_backup(
            sqlite_path=sqlite_path,
            encryption_key=None,
            output_dir=output_dir,
            now=_now(minute),
            keep=2,
        )

    remaining = list_backups(output_dir)
    assert len(remaining) == 2
    # Quedan los dos más nuevos; el último prune eliminó el de minute=1.
    assert remaining[0].name > remaining[1].name
    assert result.pruned == ("rako-db-20260704-120100.db",)


def test_create_backup_requires_existing_database(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_backup(
            sqlite_path=str(tmp_path / "missing.db"),
            encryption_key=None,
            output_dir=tmp_path / "backups",
            now=_now(),
        )


def test_create_backup_rejects_duplicate_timestamp(tmp_path: Path) -> None:
    sqlite_path = _seed_database(tmp_path)
    output_dir = tmp_path / "backups"
    create_backup(
        sqlite_path=sqlite_path,
        encryption_key=None,
        output_dir=output_dir,
        now=_now(),
    )

    with pytest.raises(FileExistsError):
        create_backup(
            sqlite_path=sqlite_path,
            encryption_key=None,
            output_dir=output_dir,
            now=_now(),
        )


def test_create_backup_rejects_invalid_keep(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="keep"):
        create_backup(
            sqlite_path=_seed_database(tmp_path),
            encryption_key=None,
            output_dir=tmp_path / "backups",
            now=_now(),
            keep=0,
        )


def test_list_backups_empty_when_dir_missing(tmp_path: Path) -> None:
    assert list_backups(tmp_path / "nope") == ()


def test_restore_replaces_database_and_keeps_pre_restore_copy(tmp_path: Path) -> None:
    from product.backup import restore_backup

    sqlite_path = _seed_database(tmp_path)
    output_dir = tmp_path / "backups"
    snapshot = create_backup(
        sqlite_path=sqlite_path,
        encryption_key=None,
        output_dir=output_dir,
        now=_now(),
    ).backup_path

    # La base sigue viva después del backup y cambia.
    db = Database.open(sqlite_path, None)
    db.config.set("preferred_name", "Otro")
    db.close()

    result = restore_backup(
        backup_path=snapshot,
        sqlite_path=sqlite_path,
        encryption_key=None,
        now=_now(1),
    )

    restored = Database.open(sqlite_path, None)
    try:
        assert restored.config.get("preferred_name") == "Nico"
    finally:
        restored.close()
    assert result.pre_restore_copy is not None
    assert result.pre_restore_copy.exists()


def test_restore_rejects_non_rako_file(tmp_path: Path) -> None:
    from product.backup import restore_backup

    bogus = tmp_path / "bogus.db"
    conn = sqlite3.connect(bogus)
    conn.execute("CREATE TABLE nada (x INTEGER)")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="user_config"):
        restore_backup(
            backup_path=bogus,
            sqlite_path=str(tmp_path / "rako.db"),
            encryption_key=None,
            now=_now(),
        )


def test_restore_missing_backup_raises(tmp_path: Path) -> None:
    from product.backup import restore_backup

    with pytest.raises(FileNotFoundError):
        restore_backup(
            backup_path=tmp_path / "nope.db",
            sqlite_path=str(tmp_path / "rako.db"),
            encryption_key=None,
            now=_now(),
        )
