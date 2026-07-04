"""Tests del TurnSession — pipeline de turno compartido entre loops de voz."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from bootstrap import build_dev_application
from config import Settings
from db.types import Interaction, InteractionType
from orchestrator.orchestrator import TurnKind, TurnResult
from orchestrator.turn_session import TurnSession
from product.user_config import UserConfigService


def _now() -> datetime:
    return datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def _settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(
        _env_file=None,
        rako_env="dev",
        sqlite_path=str(tmp_path / "rako.db"),
        anthropic_api_key=None,
        obsidian_vault_path=str(tmp_path / "vault"),
        chroma_db_path=str(tmp_path / "chroma"),
        **overrides,
    )


def _make_session(tmp_path: Path, **overrides) -> tuple[TurnSession, object]:
    app = build_dev_application(_settings(tmp_path, **overrides))
    session = TurnSession(db=app.db, settings=app.settings, now=_now)
    return session, app


def _seed_interaction(app, *, minutes_ago: int, user: str, rako: str) -> None:
    app.db.interactions.append(
        Interaction(
            id=f"seed_{minutes_ago}",
            timestamp=_now() - timedelta(minutes=minutes_ago),
            type=InteractionType.USER_VOICE,
            transcription_excerpt=user,
            emotion=None,
            response_id=None,
            response_text=rako,
        )
    )


# ---------------------------------------------------------------------------
# Restauración de memoria
# ---------------------------------------------------------------------------


def test_restore_recovers_recent_interactions_in_order(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    _seed_interaction(app, minutes_ago=10, user="hola", rako="hola, ¿cómo vas?")
    _seed_interaction(app, minutes_ago=5, user="bien", rako="me alegro")

    session.restore_recent_memory()

    lines = session.memory.lines()
    assert "Usuario: hola" in lines[0]
    assert "Rako: me alegro" in lines[-1]


def test_restore_ignores_interactions_older_than_window(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    _seed_interaction(app, minutes_ago=120, user="ayer", rako="respuesta vieja")

    session.restore_recent_memory()

    assert session.memory.lines() == ()


def test_restore_is_skipped_in_private_mode(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path, rako_mode="private")
    _seed_interaction(app, minutes_ago=5, user="hola", rako="hola")

    session.restore_recent_memory()

    assert session.memory.lines() == ()


# ---------------------------------------------------------------------------
# Comando "recuerda que ..."
# ---------------------------------------------------------------------------


def test_remember_command_stores_memory_and_confirms(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)

    confirmation = session.try_remember_command("recuerda que prefiero estudiar de noche")

    assert confirmation is not None
    assert "prefiero estudiar de noche" in confirmation
    memories = UserConfigService(app.db).list_memory()
    assert any("prefiero estudiar de noche" in m.text for m in memories)
    assert any("prefiero estudiar de noche" in line for line in session.memory.lines())


def test_non_command_transcript_returns_none(tmp_path: Path) -> None:
    session, _ = _make_session(tmp_path)

    assert session.try_remember_command("hola, ¿cómo estás?") is None
    assert session.memory.lines() == ()


def test_remember_command_with_crisis_phrase_defers_to_crisis_pipeline(
    tmp_path: Path,
) -> None:
    # Una frase de crisis dentro de un comando de memoria NO debe guardarse
    # como preferencia: el turno debe seguir al orquestador, donde el
    # detector dispara el protocolo curado.
    session, app = _make_session(tmp_path)

    result = session.try_remember_command("recuerda que ya no quiero vivir")

    assert result is None
    assert UserConfigService(app.db).list_memory() == ()


def test_remember_command_rejected_by_validation_returns_none(tmp_path: Path, monkeypatch) -> None:
    session, _ = _make_session(tmp_path)

    def _reject(self, **kwargs):
        raise ValueError("memory text cannot be empty")

    monkeypatch.setattr(UserConfigService, "add_memory", _reject)

    assert session.try_remember_command("recuerda que algo") is None
    assert session.memory.lines() == ()


def test_restore_accepts_naive_timestamps_as_utc(tmp_path: Path) -> None:
    # SQLite puede devolver timestamps sin tzinfo según el backend; la
    # ventana de restauración debe tratarlos como UTC, no crashear.
    session, app = _make_session(tmp_path)
    app.db.interactions.append(
        Interaction(
            id="naive",
            timestamp=_now().replace(tzinfo=None) - timedelta(minutes=5),
            type=InteractionType.USER_VOICE,
            transcription_excerpt="hola",
            emotion=None,
            response_id=None,
            response_text="hola, ¿cómo vas?",
        )
    )

    session.restore_recent_memory()

    assert any("hola" in line for line in session.memory.lines())


# ---------------------------------------------------------------------------
# build_turn_input — inputs de triage
# ---------------------------------------------------------------------------


def test_build_turn_input_includes_wellbeing_unit_and_conversation(
    tmp_path: Path,
) -> None:
    session, app = _make_session(tmp_path)
    UserConfigService(app.db).update_channels(
        {
            "wellbeing_unit_name": "Bienestar UDD",
            "wellbeing_unit_phone": "+56228203419",
        }
    )
    session.add_exchange(user="hola", rako="hola, ¿cómo vas?")

    turn = session.build_turn_input("me fue bien hoy")

    assert turn.wellbeing_unit_name == "Bienestar UDD"
    assert turn.wellbeing_unit_phone == "+56228203419"
    assert any("hola" in line for line in turn.user_context.recent_conversation)
    assert turn.recent_low_mood_days == 0
    assert turn.now == _now()


def test_build_turn_input_counts_recent_low_mood_days(tmp_path: Path) -> None:
    from db.types import EmotionalStateRecord
    from emotion.types import EmotionalVector

    session, app = _make_session(tmp_path)
    for day in range(3):
        app.db.emotional_states.append(
            EmotionalStateRecord(
                id=f"mood_{day}",
                at=_now() - timedelta(days=day + 1),
                vector=EmotionalVector(valence=-0.8, arousal=0.2, dominance=0.0),
                trigger_event="checkin",
                confidence=1.0,
            )
        )

    turn = session.build_turn_input("no sé si vale la pena seguir estudiando esto")

    assert turn.recent_low_mood_days == 3


# ---------------------------------------------------------------------------
# complete_turn — memoria + persistencia con gate de privacidad
# ---------------------------------------------------------------------------


def _result(text: str) -> TurnResult:
    return TurnResult(
        kind=TurnKind.LLM_RESPONSE,
        text=text,
        audio_path=None,
        rag_chunk_ids=(),
        notify_contact=False,
        show_resources=False,
    )


def test_complete_turn_persists_interaction_and_updates_memory(
    tmp_path: Path,
) -> None:
    session, app = _make_session(tmp_path)

    session.complete_turn(transcript="hola rako", result=_result("hola, ¿cómo vas?"), now=_now())

    stored = app.db.interactions.list_recent(limit=5)
    assert len(stored) == 1
    assert stored[0].transcription_excerpt == "hola rako"
    assert stored[0].response_text == "hola, ¿cómo vas?"
    assert any("hola rako" in line for line in session.memory.lines())


def test_complete_turn_does_not_persist_in_private_mode(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path, rako_mode="private")

    session.complete_turn(transcript="hola rako", result=_result("hola"), now=_now())

    assert app.db.interactions.list_recent(limit=5) == []
    # La memoria en proceso sí funciona: privacidad es no persistir.
    assert any("hola rako" in line for line in session.memory.lines())
