"""Tests del sistema de migraciones versionadas."""

from __future__ import annotations

from pathlib import Path

import pytest

from db.database import Database
from db.migrations import (
    MIGRATIONS,
    SCHEMA_VERSION,
    SchemaTooNewError,
    apply_migrations,
    get_schema_version,
)


def test_fresh_database_lands_on_latest_version(tmp_path: Path) -> None:
    db = Database.open(str(tmp_path / "rako.db"), None)
    try:
        assert get_schema_version(db._conn) == SCHEMA_VERSION
    finally:
        db.close()


def test_second_open_applies_nothing(tmp_path: Path) -> None:
    path = str(tmp_path / "rako.db")
    Database.open(path, None).close()

    db = Database.open(path, None)
    try:
        assert apply_migrations(db._conn) == ()
    finally:
        db.close()


def test_pre_migrations_database_is_stamped_without_data_loss(tmp_path: Path) -> None:
    path = str(tmp_path / "rako.db")
    # Simula una base creada antes del sistema de migraciones: esquema
    # actual pero user_version=0, con datos reales.
    db = Database.open(path, None)
    db.config.set("preferred_name", "Nico")
    db._conn.execute("PRAGMA user_version = 0")
    db.close()

    reopened = Database.open(path, None)
    try:
        assert get_schema_version(reopened._conn) == SCHEMA_VERSION
        assert reopened.config.get("preferred_name") == "Nico"
    finally:
        reopened.close()


def test_newer_database_than_code_aborts(tmp_path: Path) -> None:
    path = str(tmp_path / "rako.db")
    db = Database.open(path, None)
    db._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 5}")
    db.close()

    with pytest.raises(SchemaTooNewError, match="git pull"):
        Database.open(path, None)


def test_migrations_are_contiguous_from_one() -> None:
    versions = [migration.version for migration in MIGRATIONS]
    assert versions == list(range(1, len(MIGRATIONS) + 1))
    assert versions[-1] == SCHEMA_VERSION
