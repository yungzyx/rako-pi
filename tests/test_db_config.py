"""Tests del ConfigRepository — settings clave/valor."""

from __future__ import annotations

from db.repositories import ConfigRepository


def test_get_returns_none_when_missing(db_conn) -> None:
    repo = ConfigRepository(db_conn)

    assert repo.get("missing") is None


def test_set_then_get(db_conn) -> None:
    repo = ConfigRepository(db_conn)
    repo.set("theme", "dark")

    assert repo.get("theme") == "dark"


def test_set_overwrites_existing(db_conn) -> None:
    repo = ConfigRepository(db_conn)
    repo.set("theme", "dark")
    repo.set("theme", "light")

    assert repo.get("theme") == "light"


def test_delete_removes_entry(db_conn) -> None:
    repo = ConfigRepository(db_conn)
    repo.set("theme", "dark")

    assert repo.delete("theme") is True
    assert repo.get("theme") is None


def test_delete_returns_false_when_missing(db_conn) -> None:
    repo = ConfigRepository(db_conn)

    assert repo.delete("missing") is False


def test_get_all_returns_dict(db_conn) -> None:
    repo = ConfigRepository(db_conn)
    repo.set("theme", "dark")
    repo.set("language", "es-CL")

    all_ = repo.get_all()

    assert all_ == {"theme": "dark", "language": "es-CL"}


def test_purge_all(db_conn) -> None:
    repo = ConfigRepository(db_conn)
    repo.set("a", "1")
    repo.set("b", "2")

    deleted = repo.purge_all()

    assert deleted == 2
    assert repo.get_all() == {}
