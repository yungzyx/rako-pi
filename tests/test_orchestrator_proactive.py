"""Tests del monitor proactivo — decisión determinística con salvaguardas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from bootstrap import build_dev_application
from config import Settings
from db.types import Interaction, InteractionType
from orchestrator.proactive import decide_proactive_nudge, record_nudge
from safety.types import CrisisLevel, CrisisReason, CrisisSignal


def _now() -> datetime:
    # 15:00 Chile continental (UTC-4 en esa fecha) — fuera del horario silencioso.
    return datetime(2026, 7, 4, 19, 0, tzinfo=UTC)


def _app(tmp_path: Path, **overrides):
    return build_dev_application(
        Settings(
            _env_file=None,
            rako_env="dev",
            sqlite_path=str(tmp_path / "rako.db"),
            anthropic_api_key=None,
            obsidian_vault_path=str(tmp_path / "vault"),
            chroma_db_path=str(tmp_path / "chroma"),
            **overrides,
        )
    )


def _decide(app, *, now=None, **overrides):
    defaults = dict(
        now=now or _now(),
        rako_mode=app.settings.rako_mode,
        do_not_disturb_start="22:00",
        do_not_disturb_end="08:00",
    )
    defaults.update(overrides)
    return decide_proactive_nudge(app.db, **defaults)


def _seed_pending_task(app) -> None:
    from db.types import Task, TaskSource, TaskStatus

    app.db.tasks.create(
        Task(
            id="t_pending",
            title="informe de redes",
            description=None,
            parent_id=None,
            status=TaskStatus.TODO,
            created_at=_now() - timedelta(days=1),
            completed_at=None,
            source=TaskSource.VOICE,
        )
    )


def _seed_interaction(app, *, hours_ago: float) -> None:
    app.db.interactions.append(
        Interaction(
            id=f"i_{hours_ago}",
            timestamp=_now() - timedelta(hours=hours_ago),
            type=InteractionType.USER_VOICE,
            transcription_excerpt="hola",
            emotion=None,
            response_id=None,
            response_text="hola",
        )
    )


def test_nudges_when_pending_tasks_and_long_inactivity(tmp_path: Path) -> None:
    app = _app(tmp_path)
    _seed_pending_task(app)
    _seed_interaction(app, hours_ago=5)

    decision = _decide(app)

    assert decision.should_nudge
    assert decision.reason == "pending_without_activity"
    assert decision.nudge_text


def test_private_mode_disables_monitor(tmp_path: Path) -> None:
    app = _app(tmp_path, rako_mode="private")

    assert _decide(app).reason == "private_mode"


def test_recent_crisis_blocks_nudges(tmp_path: Path) -> None:
    app = _app(tmp_path)
    _seed_pending_task(app)
    _seed_interaction(app, hours_ago=5)
    app.db.crisis_journal.record(
        CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.KEYWORDS_IDEATION,),
            detected_at=_now() - timedelta(hours=2),
        )
    )

    assert _decide(app).reason == "recent_crisis"


def test_quiet_hours_block_nudges_in_user_timezone(tmp_path: Path) -> None:
    app = _app(tmp_path)
    _seed_pending_task(app)
    _seed_interaction(app, hours_ago=5)
    # 03:00 UTC = 23:00 en Chile (UTC-4): dentro de la ventana 22:00-08:00.
    night = datetime(2026, 7, 5, 3, 0, tzinfo=UTC)
    _seed_interaction(app, hours_ago=-3)  # mantener inactividad relativa

    decision = _decide(app, now=night)

    assert decision.reason == "quiet_hours"


def test_rate_limit_min_interval_and_daily_cap(tmp_path: Path) -> None:
    app = _app(tmp_path)
    _seed_pending_task(app)
    _seed_interaction(app, hours_ago=6)

    record_nudge(app.db, now=_now() - timedelta(hours=1))
    assert _decide(app).reason == "too_soon"

    record_nudge(app.db, now=_now() - timedelta(hours=5))
    assert _decide(app, min_interval_hours=4.0).reason == "daily_cap"


def test_no_signal_paths(tmp_path: Path) -> None:
    app = _app(tmp_path)
    # Sin tareas pendientes.
    assert _decide(app).reason == "no_pending_tasks"
    # Con tareas pero sin uso histórico del dispositivo.
    _seed_pending_task(app)
    assert _decide(app).reason == "never_used"
    # Con uso reciente: no molestar.
    _seed_interaction(app, hours_ago=1)
    assert _decide(app).reason == "recently_active"
