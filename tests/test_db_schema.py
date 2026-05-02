"""Tests del DDL del estado local."""

from __future__ import annotations

from db.connection import open_connection
from db.schema import EXPECTED_TABLES, create_all


def _table_names(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row["name"] for row in rows}


def test_create_all_creates_every_expected_table() -> None:
    conn = open_connection(":memory:")

    create_all(conn)

    tables = _table_names(conn)
    for expected in EXPECTED_TABLES:
        assert expected in tables, f"missing table: {expected}"


def test_create_all_is_idempotent() -> None:
    conn = open_connection(":memory:")

    create_all(conn)
    create_all(conn)
    create_all(conn)

    tables = _table_names(conn)
    for expected in EXPECTED_TABLES:
        assert expected in tables


def test_tasks_supports_self_referencing_parent_id() -> None:
    conn = open_connection(":memory:")
    create_all(conn)

    conn.execute(
        "INSERT INTO tasks (id, title, status, created_at, source) "
        "VALUES (?, ?, ?, ?, ?)",
        ("p1", "parent", "TODO", "2026-05-01T18:00:00+00:00", "VOICE"),
    )
    conn.execute(
        "INSERT INTO tasks (id, title, parent_id, status, created_at, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("c1", "child", "p1", "TODO", "2026-05-01T18:01:00+00:00", "VOICE"),
    )
    conn.commit()

    rows = conn.execute("SELECT id, parent_id FROM tasks").fetchall()
    assert {(r["id"], r["parent_id"]) for r in rows} == {("p1", None), ("c1", "p1")}


def test_user_config_key_is_unique() -> None:
    conn = open_connection(":memory:")
    create_all(conn)

    conn.execute(
        "INSERT INTO user_config (key, value, updated_at) VALUES (?, ?, ?)",
        ("theme", "dark", "2026-05-01T18:00:00+00:00"),
    )
    conn.commit()

    import sqlite3

    import pytest

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO user_config (key, value, updated_at) VALUES (?, ?, ?)",
            ("theme", "light", "2026-05-01T18:01:00+00:00"),
        )
        conn.commit()
