from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db.database import Database
from db.types import TaskStatus
from orchestrator.context import build_user_context
from product.user_config import UserConfigService
from productivity.focus import create_focus_task


def test_build_user_context_uses_tasks_and_normal_user_memory(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("leer papers", now - timedelta(hours=1)))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=now)
    db.tasks.create(create_focus_task("programar", now))
    config = UserConfigService(db)
    config.add_memory(text="Prefiere bloques de 25 minutos", category="routine", now=now)
    config.update_consent({"sensitive_memory_enabled": True}, now=now)
    config.add_memory(
        text="Dato sensible que no debe salir",
        category="boundary",
        sensitivity="sensitive",
        now=now,
    )

    context = build_user_context(
        db,
        now,
        recent_conversation=("Usuario: sigamos",),
    )

    assert context.pending_task_count == 1
    assert context.recent_completion_count == 1
    assert context.recent_conversation == ("Usuario: sigamos",)
    assert context.user_memory == ("routine: Prefiere bloques de 25 minutos",)
    assert "Dato sensible" not in " ".join(context.user_memory)
