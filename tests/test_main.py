"""Tests del CLI — smoke tests de los subcomandos."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

import main as cli_module


def _common_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path / "missing-vault"))
    monkeypatch.setenv("RAKO_ENV", "dev")


def test_demo_turn_prints_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    exit_code = cli_module.cli(["demo-turn", "me siento atascado"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Estoy" in captured.out or "Aquí" in captured.out or "Rako" in captured.out


def test_demo_crisis_panic_invokes_protocol(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    exit_code = cli_module.cli(["demo-crisis-panic"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "crisis" in captured.out.lower() or "protocolo" in captured.out.lower()
    assert "PANIC_BUTTON" in captured.out or "panic" in captured.out.lower()


def test_purge_all_clears_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    # Sembrar algo primero.
    cli_module.cli(["demo-crisis-panic"])
    capsys.readouterr()

    exit_code = cli_module.cli(["purge-all"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert (
        "borrado" in captured.out.lower()
        or "deleted" in captured.out.lower()
        or "purg" in captured.out.lower()
    )


def test_help_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_module.cli(["--help"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "demo-turn" in captured.out


def test_unknown_subcommand_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_module.cli(["nonexistent-command"])

    assert exc.value.code != 0


def test_reindex_rag_indexes_real_vault(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "01.md").write_text("---\ncategoria: test\n---\n\n# t\n\n## A\n\ncuerpo de prueba.\n")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.setenv("CHROMA_DB_PATH", str(tmp_path / "chroma"))

    exit_code = cli_module.cli(["reindex-rag"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "indexados" in captured.out.lower()


def test_bootstrap_uses_chroma_retriever_when_index_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from rag.chroma_retriever import ChromaRetriever
    from rag.indexer import index_chunks
    from rag.types import Chunk

    db_path = str(tmp_path / "chroma")
    index_chunks(
        chunks=(Chunk(id="a#0", text="x", metadata={"source": "a"}),),
        db_path=db_path,
        collection_name="rako_kb",
    )

    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CHROMA_DB_PATH", db_path)

    from bootstrap import build_dev_application
    from config import Settings

    app = build_dev_application(Settings())
    try:
        assert isinstance(app.retriever, ChromaRetriever)
    finally:
        app.close()


def test_demo_turn_prints_rag_chunks_when_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    # Inyectar un chunk al retriever para que el print de rag_chunks dispare.
    from datetime import datetime

    from bootstrap import build_dev_application
    from config import Settings
    from orchestrator.orchestrator import TurnInput
    from orchestrator.types import UserContext
    from rag.client import InMemoryRetriever
    from rag.types import Chunk

    app = build_dev_application(Settings())
    app.orchestrator._retriever = InMemoryRetriever(  # type: ignore[attr-defined]
        [Chunk(id="01#0", text="respira profundo", metadata={})]
    )
    now = datetime.now(UTC)
    turn = TurnInput(
        transcript="respira",
        emotion=None,
        panic_button=None,
        emotion_history=(),
        last_high_distress_at=None,
        last_interaction_at=None,
        user_context=UserContext(
            pending_task_count=0,
            recent_completion_count=0,
            robot_level=1,
            time_of_day="tarde",
            recent_mood_summary=None,
        ),
        now=now,
    )
    result = app.orchestrator.handle_turn(turn)
    app.close()

    assert "01#0" in result.rag_chunk_ids


@pytest.mark.parametrize(
    "hour,expected",
    [(8, "mañana"), (15, "tarde"), (23, "noche"), (3, "noche")],
)
def test_default_user_context_time_of_day(hour: int, expected: str) -> None:
    from datetime import datetime

    from orchestrator.types import default_user_context

    now = datetime(2026, 5, 1, hour, 0, tzinfo=UTC)
    ctx = default_user_context(now)

    assert ctx.time_of_day == expected


def test_run_subcommand_executes_finite_iterations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    exit_code = cli_module.cli(["run", "--max-iterations", "2"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "loop principal" in captured.out.lower()


def test_run_command_aborts_when_prod_lacks_encryption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # CLAUDE.md §4.1.6: producción no debe correr sin SQLCipher activo — el
    # arranque debe abortar antes de aceptar el loop de voz real. En este
    # sandbox no hay libsqlcipher instalado, así que `rako_env=prod` sin key
    # siempre debe fallar el self-test de cifrado.
    _common_env(monkeypatch, tmp_path)
    monkeypatch.setenv("RAKO_ENV", "prod")
    monkeypatch.delenv("SQLITE_ENCRYPTION_KEY", raising=False)

    exit_code = cli_module.cli(["run", "--max-iterations", "2"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ABORT" in captured.err
    assert "not encrypted" in captured.err.lower()


def test_smart_checkin_reports_consent_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _common_env(monkeypatch, tmp_path)

    exit_code = cli_module.cli(["smart-checkin", "--at", "2026-06-20T14:00:00+00:00"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "decision=consent_required" in captured.out


def test_smart_checkin_dry_run_does_not_record_send(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from db.database import Database
    from product.user_config import UserConfigService

    _common_env(monkeypatch, tmp_path)
    db = Database.open(str(tmp_path / "rako.db"))
    try:
        config = UserConfigService(db)
        config.update_channels({"whatsapp_number": "+56912345678"})
        config.update_consent({"whatsapp_enabled": True, "proactive_messages_enabled": True})
    finally:
        db.close()

    exit_code = cli_module.cli(["smart-checkin", "--dry-run", "--at", "2026-06-20T14:00:00+00:00"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "decision=eligible" in captured.out
    assert "recommendation=" in captured.out

    db = Database.open(str(tmp_path / "rako.db"))
    try:
        assert db.config.get("whatsapp.last_checkin") is None
    finally:
        db.close()


def test_smart_checkin_records_send_when_eligible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from db.database import Database
    from product.user_config import UserConfigService

    _common_env(monkeypatch, tmp_path)
    db = Database.open(str(tmp_path / "rako.db"))
    try:
        config = UserConfigService(db)
        config.update_channels({"whatsapp_number": "+56912345678"})
        config.update_consent({"whatsapp_enabled": True, "proactive_messages_enabled": True})
    finally:
        db.close()

    exit_code = cli_module.cli(["smart-checkin", "--at", "2026-06-20T14:00:00+00:00"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "sent_kind=SMART_CHECKIN" in captured.out

    db = Database.open(str(tmp_path / "rako.db"))
    try:
        assert db.config.get("whatsapp.last_checkin") is not None
    finally:
        db.close()


def test_select_builder_returns_pi_when_prod() -> None:
    from bootstrap import build_pi_application
    from config import Settings
    from main import _select_builder

    settings = Settings(_env_file=None, rako_env="prod")
    assert _select_builder(settings) is build_pi_application


def test_select_builder_returns_dev_when_dev() -> None:
    from bootstrap import build_dev_application
    from config import Settings
    from main import _select_builder

    settings = Settings(_env_file=None, rako_env="dev")
    assert _select_builder(settings) is build_dev_application


def test_select_builder_returns_dev_when_staging() -> None:
    from bootstrap import build_dev_application
    from config import Settings
    from main import _select_builder

    settings = Settings(_env_file=None, rako_env="staging")
    assert _select_builder(settings) is build_dev_application


def test_cli_uses_pi_builder_when_rako_env_prod(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """En prod, el CLI debe rutear a build_pi_application aunque las libs
    Pi no estén instaladas (caída elegante a fakes)."""
    _common_env(monkeypatch, tmp_path)
    monkeypatch.setenv("RAKO_ENV", "prod")

    called: list[str] = []

    import bootstrap as bootstrap_module

    real_pi = bootstrap_module.build_pi_application

    def spy_pi(settings):
        called.append("pi")
        return real_pi(settings)

    monkeypatch.setattr(cli_module, "build_pi_application", spy_pi, raising=False)
    monkeypatch.setattr(bootstrap_module, "build_pi_application", spy_pi)

    exit_code = cli_module.cli(["demo-turn", "hola"])

    assert exit_code == 0
    assert called == ["pi"]
