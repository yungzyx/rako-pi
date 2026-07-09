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
    # El historial también viaja como PARES (user, rako) para mandarlo al LLM
    # como turnos reales — esta es la cadena completa del fix de seguimiento.
    assert ("hola", "hola, ¿cómo vas?") in turn.user_context.conversation_turns
    assert turn.recent_low_mood_days == 0
    assert turn.now == _now()


def test_build_turn_input_carries_prior_exchange_as_turns_after_complete_turn(
    tmp_path: Path,
) -> None:
    # Extremo a extremo: un turno completado alimenta el conversation_turns del
    # siguiente build_turn_input (memory.turns() → build_user_context → LLM).
    session, _ = _make_session(tmp_path)
    session.complete_turn(
        transcript="quiero estudiar cálculo",
        result=_result("Dale, ¿qué tema te complica?"),
        now=_now(),
    )

    turn = session.build_turn_input("las derivadas")

    assert ("quiero estudiar cálculo", "Dale, ¿qué tema te complica?") in (
        turn.user_context.conversation_turns
    )


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


# ---------------------------------------------------------------------------
# Trigger de inactividad post-angustia (antes dormido) — datos vivos
# ---------------------------------------------------------------------------


def _record_crisis(app, *, hours_ago: int) -> None:
    from safety.types import CrisisLevel, CrisisReason, CrisisSignal

    app.db.crisis_journal.record(
        CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.KEYWORDS_IDEATION,),
            detected_at=_now() - timedelta(hours=hours_ago),
        )
    )


def test_turn_input_carries_live_distress_and_interaction_signals(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    _record_crisis(app, hours_ago=3)
    _seed_interaction(app, minutes_ago=180, user="antes", rako="respuesta")

    turn = session.build_turn_input("hola rako")

    assert turn.last_high_distress_at == _now() - timedelta(hours=3)
    assert turn.last_interaction_at == _now() - timedelta(minutes=180)


def test_inactivity_after_distress_reaches_curated_followup(tmp_path: Path) -> None:
    # Crisis hace 3h, ninguna interacción desde entonces, y el usuario
    # aprieta el botón: el turno debe ir al protocolo curado de
    # seguimiento, no al LLM.
    from orchestrator.orchestrator import TurnKind

    session, app = _make_session(tmp_path)
    _record_crisis(app, hours_ago=3)
    _seed_interaction(app, minutes_ago=180, user="antes", rako="respuesta")

    turn = session.build_turn_input("hola, quiero estudiar")
    result = app.orchestrator.handle_turn(turn)

    assert result.kind is TurnKind.CRISIS_PROTOCOL
    assert result.metadata.get("response_id") == "inactivity_followup"


def test_followup_events_do_not_renew_distress_window(tmp_path: Path) -> None:
    # Un evento cuyo único motivo es el follow-up de inactividad NO debe
    # contar como angustia nueva — si contara, cada seguimiento renovaría
    # la ventana de 24h y el ciclo no terminaría nunca.
    from safety.types import CrisisLevel, CrisisReason, CrisisSignal

    session, app = _make_session(tmp_path)
    app.db.crisis_journal.record(
        CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.PROLONGED_INACTIVITY_AFTER_DISTRESS,),
            detected_at=_now() - timedelta(hours=1),
        )
    )

    turn = session.build_turn_input("hola")

    assert turn.last_high_distress_at is None


def test_no_signals_keeps_trigger_off(tmp_path: Path) -> None:
    session, _ = _make_session(tmp_path)

    turn = session.build_turn_input("hola")

    assert turn.last_high_distress_at is None
    assert turn.last_interaction_at is None


# ---------------------------------------------------------------------------
# Aprendizaje opt-in de preferencias — sugerir, confirmar, declinar
# ---------------------------------------------------------------------------


def test_llm_turn_with_preference_produces_suggestion(tmp_path: Path) -> None:
    session, _ = _make_session(tmp_path)

    suggestion = session.suggest_preference(
        "para las pruebas prefiero estudiar de noche", _result("buena idea")
    )

    assert suggestion is not None
    assert "prefiero estudiar de noche" in suggestion
    assert "recuérdalo" in suggestion


def test_confirmation_saves_pending_preference(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    session.suggest_preference("prefiero estudiar de noche siempre", _result("ok"))

    reply = session.try_remember_command("sí, recuérdalo")

    assert reply is not None and "recordar" in reply
    memories = UserConfigService(app.db).list_memory()
    assert any("prefiero estudiar de noche" in m.text for m in memories)
    # Confirmar de nuevo no debe duplicar: la pendiente ya se consumió.
    assert session.try_remember_command("sí, recuérdalo") is None


def test_decline_clears_pending_without_saving(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    session.suggest_preference("prefiero estudiar de noche siempre", _result("ok"))

    reply = session.try_remember_command("no gracias")

    assert reply is not None and "no lo guardo" in reply
    assert UserConfigService(app.db).list_memory() == ()


def test_no_suggestion_for_non_llm_turns(tmp_path: Path) -> None:
    from orchestrator.orchestrator import TurnKind, TurnResult

    session, _ = _make_session(tmp_path)
    referral = TurnResult(
        kind=TurnKind.WELLBEING_REFERRAL,
        text="derivación",
        audio_path=None,
        rag_chunk_ids=(),
        notify_contact=False,
        show_resources=False,
    )

    assert session.suggest_preference("prefiero estudiar de noche siempre", referral) is None


def test_no_suggestion_when_similar_memory_exists(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    UserConfigService(app.db).add_memory(text="prefiero estudiar de noche", category="preference")

    suggestion = session.suggest_preference(
        "ya te dije que prefiero estudiar de noche", _result("sí")
    )

    assert suggestion is None


def test_plain_turns_do_not_suggest(tmp_path: Path) -> None:
    session, _ = _make_session(tmp_path)

    assert session.suggest_preference("hola, ¿cómo estás?", _result("hola")) is None


def test_pending_memory_rejected_by_validation_returns_none(tmp_path: Path, monkeypatch) -> None:
    session, _ = _make_session(tmp_path)
    session.suggest_preference("prefiero estudiar de noche siempre", _result("ok"))

    def _reject(self, **kwargs):
        raise ValueError("invalid")

    monkeypatch.setattr(UserConfigService, "add_memory", _reject)

    assert session.try_remember_command("sí, recuérdalo") is None


def test_unrelated_turn_keeps_pending_suggestion_alive(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    session.suggest_preference("prefiero estudiar de noche siempre", _result("ok"))

    # Un turno cualquiera no confirma ni declina: la pendiente sigue viva.
    assert session.try_remember_command("¿qué hora es?") is None
    reply = session.try_remember_command("recuérdalo")

    assert reply is not None
    assert any(
        "prefiero estudiar de noche" in m.text for m in UserConfigService(app.db).list_memory()
    )


def test_pending_memory_corrupt_or_expired_is_discarded(tmp_path: Path) -> None:
    from datetime import timedelta as _td

    session, app = _make_session(tmp_path)

    # JSON corrupto.
    app.db.config.set("voice.pending_memory", "{no es json")
    assert session.try_remember_command("sí, recuérdalo") is None

    # Payload que no es dict.
    app.db.config.set("voice.pending_memory", "[1, 2]")
    assert session.try_remember_command("sí, recuérdalo") is None

    # Expirada.
    import json as _json

    app.db.config.set(
        "voice.pending_memory",
        _json.dumps(
            {
                "text": "prefiero estudiar de noche",
                "expires_at": (_now() - _td(minutes=1)).isoformat(),
            }
        ),
    )
    assert session.try_remember_command("sí, recuérdalo") is None
    assert UserConfigService(app.db).list_memory() == ()


# ---------------------------------------------------------------------------
# Aftercare post-crisis: build_turn_input expone la última crisis y el turno
# de seguimiento no vuelve al LLM
# ---------------------------------------------------------------------------


def _record_crisis_minutes_ago(app, *, minutes_ago: int) -> None:
    from safety.types import CrisisLevel, CrisisReason, CrisisSignal

    app.db.crisis_journal.record(
        CrisisSignal(
            level=CrisisLevel.CRISIS,
            reasons=(CrisisReason.KEYWORDS_IDEATION,),
            detected_at=_now() - timedelta(minutes=minutes_ago),
        )
    )


def test_turn_input_carries_recent_crisis_for_aftercare(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    _record_crisis_minutes_ago(app, minutes_ago=5)

    turn = session.build_turn_input("no se que hacer")

    assert turn.recent_crisis_at == _now() - timedelta(minutes=5)


def test_recent_crisis_followup_reaches_aftercare(tmp_path: Path) -> None:
    session, app = _make_session(tmp_path)
    _record_crisis_minutes_ago(app, minutes_ago=3)

    # El turno siguiente a la crisis se acompaña en modo aftercare (LLM acotado
    # por el hint, adaptativo), no en el flujo normal de productividad.
    turn = session.build_turn_input("no quiero contactar a nadie, no se que hacer")
    result = app.orchestrator.handle_turn(turn)

    assert result.kind is TurnKind.CRISIS_AFTERCARE
    assert result.metadata.get("aftercare") is True


def test_aftercare_protects_even_in_private_mode(tmp_path: Path) -> None:
    # El journal de crisis se escribe también en modo privado (evento de
    # seguridad), así que el aftercare protege igual.
    session, app = _make_session(tmp_path, rako_mode="private")
    _record_crisis_minutes_ago(app, minutes_ago=2)

    turn = session.build_turn_input("no se que hacer")
    result = app.orchestrator.handle_turn(turn)

    assert result.kind is TurnKind.CRISIS_AFTERCARE
