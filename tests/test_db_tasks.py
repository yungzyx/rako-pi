"""Tests del TaskRepository."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from db.repositories import TaskRepository
from db.types import Task, TaskSource, TaskStatus

UTC = UTC


def _new_task(
    *,
    id: str = "t1",
    title: str = "Estudiar capítulo 3",
    description: str | None = None,
    parent_id: str | None = None,
    status: TaskStatus = TaskStatus.TODO,
    source: TaskSource = TaskSource.VOICE,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Task:
    return Task(
        id=id,
        title=title,
        description=description,
        parent_id=parent_id,
        status=status,
        created_at=created_at or datetime(2026, 5, 1, 18, 0, tzinfo=UTC),
        completed_at=completed_at,
        source=source,
    )


def test_create_persists_and_returns_task(db_conn) -> None:
    repo = TaskRepository(db_conn)
    task = _new_task()

    saved = repo.create(task)

    assert saved == task
    assert repo.find_by_id(task.id) == task


def test_find_by_id_returns_none_when_missing(db_conn) -> None:
    repo = TaskRepository(db_conn)

    assert repo.find_by_id("missing") is None


def test_list_by_status_filters_correctly(db_conn) -> None:
    repo = TaskRepository(db_conn)
    repo.create(_new_task(id="a", status=TaskStatus.TODO))
    repo.create(_new_task(id="b", status=TaskStatus.DONE))
    repo.create(_new_task(id="c", status=TaskStatus.TODO))

    todo_tasks = repo.list_by_status(TaskStatus.TODO)

    assert {t.id for t in todo_tasks} == {"a", "c"}


def test_list_pending_returns_todo_and_in_progress(db_conn) -> None:
    repo = TaskRepository(db_conn)
    repo.create(_new_task(id="a", status=TaskStatus.TODO))
    repo.create(_new_task(id="b", status=TaskStatus.IN_PROGRESS))
    repo.create(_new_task(id="c", status=TaskStatus.DONE))
    repo.create(_new_task(id="d", status=TaskStatus.CANCELLED))

    pending = repo.list_pending()

    assert {t.id for t in pending} == {"a", "b"}


def test_list_children_returns_only_children(db_conn) -> None:
    repo = TaskRepository(db_conn)
    repo.create(_new_task(id="parent"))
    repo.create(_new_task(id="child1", parent_id="parent"))
    repo.create(_new_task(id="child2", parent_id="parent"))
    repo.create(_new_task(id="other"))

    children = repo.list_children("parent")

    assert {t.id for t in children} == {"child1", "child2"}


def test_update_status_returns_new_task(db_conn) -> None:
    repo = TaskRepository(db_conn)
    task = repo.create(_new_task(id="a", status=TaskStatus.TODO))
    completed_at = datetime(2026, 5, 1, 19, 0, tzinfo=UTC)

    updated = repo.update_status(task.id, TaskStatus.DONE, completed_at=completed_at)

    assert updated.status is TaskStatus.DONE
    assert updated.completed_at == completed_at
    # Inmutabilidad: el original no cambia.
    assert task.status is TaskStatus.TODO


def test_update_status_raises_for_missing_task(db_conn) -> None:
    repo = TaskRepository(db_conn)

    with pytest.raises(KeyError):
        repo.update_status("missing", TaskStatus.DONE)


def test_delete_removes_task(db_conn) -> None:
    repo = TaskRepository(db_conn)
    repo.create(_new_task(id="a"))

    deleted = repo.delete("a")

    assert deleted is True
    assert repo.find_by_id("a") is None


def test_delete_returns_false_for_missing_task(db_conn) -> None:
    repo = TaskRepository(db_conn)

    assert repo.delete("missing") is False


def test_purge_all_clears_table(db_conn) -> None:
    repo = TaskRepository(db_conn)
    repo.create(_new_task(id="a"))
    repo.create(_new_task(id="b"))

    deleted = repo.purge_all()

    assert deleted == 2
    assert repo.list_pending() == []


def test_create_rejects_duplicate_id(db_conn) -> None:
    repo = TaskRepository(db_conn)
    repo.create(_new_task(id="a"))

    with pytest.raises(Exception):
        repo.create(_new_task(id="a"))


def test_cascade_delete_removes_children(db_conn) -> None:
    repo = TaskRepository(db_conn)
    repo.create(_new_task(id="parent"))
    repo.create(_new_task(id="child", parent_id="parent"))

    repo.delete("parent")

    assert repo.find_by_id("child") is None
