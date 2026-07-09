from __future__ import annotations

from datetime import UTC, datetime, timedelta

from channels.whatsapp.client import InMemoryWhatsAppClient
from channels.whatsapp.service import WhatsAppService
from db.database import Database
from db.types import TaskStatus
from product.user_config import UserConfigService
from productivity.focus import create_focus_task


def _enable_whatsapp(db: Database, *, progress: bool = False) -> None:
    config = UserConfigService(db)
    config.update_channels({"whatsapp_number": "+56912345678"})
    config.update_consent({"whatsapp_enabled": True, "progress_reports_enabled": progress})


def _enable_proactive_whatsapp(db: Database, *, progress: bool = False) -> None:
    config = UserConfigService(db)
    config.update_channels({"whatsapp_number": "+56912345678"})
    config.update_consent(
        {
            "whatsapp_enabled": True,
            "proactive_messages_enabled": True,
            "progress_reports_enabled": progress,
        }
    )


def test_send_checkin_uses_safe_short_prompt(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)
    now = datetime(2026, 6, 1, 16, 0, tzinfo=UTC)

    message = service.send_checkin(to="+56912345678", now=now)

    assert message.kind == "CHECKIN"
    assert message.to == "+56912345678"
    assert "¿cómo te sientes" in message.text
    assert db.config.get("whatsapp.last_checkin") is not None


def test_send_checkin_requires_whatsapp_consent(db_conn) -> None:
    db = Database(db_conn)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    message = service.send_checkin(to="+56912345678")

    assert message.kind == "CONSENT_REQUIRED"
    assert db.config.get("whatsapp.last_checkin") is None


def test_handle_inbound_records_low_mood_and_replies(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)
    now = datetime(2026, 6, 1, 16, 0, tzinfo=UTC)

    result = service.handle_inbound(from_number="+56912345678", text="me siento bajo", now=now)
    samples = db.emotional_states.list_samples_in_window(end=now, lookback=timedelta(minutes=1))

    assert result.action == "MOOD_RECORDED"
    assert result.stored_mood == "low"
    assert samples[0].vector.valence < 0
    assert client.sent[-1].kind == "MOOD_RECORDED"


def test_handle_inbound_manages_editable_memory(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)

    added = service.handle_inbound(
        from_number="+56912345678",
        text="recuerda que prefiero bloques de 25 minutos",
    )
    listed = service.handle_inbound(from_number="+56912345678", text="qué sabes de mí")
    deleted = service.handle_inbound(from_number="+56912345678", text="olvida bloques de 25")
    listed_after_delete = service.handle_inbound(from_number="+56912345678", text="memoria")

    assert added.action == "MEMORY_ADDED"
    assert "prefiero bloques de 25 minutos" in added.response_text
    assert listed.action == "MEMORY_LIST"
    assert "prefiero bloques de 25 minutos" in listed.response_text
    assert deleted.action == "MEMORY_DELETED"
    assert listed_after_delete.action == "MEMORY_LIST"
    assert "Todavía no tengo recuerdos" in listed_after_delete.response_text


def test_handle_inbound_memory_list_excludes_sensitive_entries(db_conn) -> None:
    # Justo el dato considerado demasiado sensible para el contexto del LLM
    # (orchestrator/context.py) no debe terminar en los servidores de Meta.
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_consent({"sensitive_memory_enabled": True})
    config.add_memory(text="Prefiero bloques de 25 minutos", sensitivity="normal")
    config.add_memory(text="Me cuesta pedir ayuda cuando estoy mal", sensitivity="sensitive")
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    listed = service.handle_inbound(from_number="+56912345678", text="mis recuerdos")

    assert listed.action == "MEMORY_LIST"
    assert "Prefiero bloques de 25 minutos" in listed.response_text
    assert "Me cuesta pedir ayuda" not in listed.response_text
    assert "1 recuerdo" in listed.response_text


def test_handle_inbound_memory_list_all_sensitive_shows_only_count(db_conn) -> None:
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_consent({"sensitive_memory_enabled": True})
    config.add_memory(text="Me cuesta pedir ayuda cuando estoy mal", sensitivity="sensitive")
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    listed = service.handle_inbound(from_number="+56912345678", text="mis recuerdos")

    assert listed.action == "MEMORY_LIST"
    assert "Me cuesta pedir ayuda" not in listed.response_text
    assert "1 recuerdo" in listed.response_text


def test_handle_inbound_starts_focus_from_whatsapp_text(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)
    now = datetime(2026, 6, 1, 16, 0, tzinfo=UTC)

    result = service.handle_inbound(
        from_number="+56912345678",
        text="quiero estudiar cálculo 25 minutos",
        now=now,
    )

    assert result.action == "FOCUS"
    assert result.focus_session_id is not None
    assert "25 minutos para estudiar cálculo" in result.response_text


def test_handle_inbound_crisis_uses_curated_response(db_conn) -> None:
    db = Database(db_conn)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)

    result = service.handle_inbound(
        from_number="+56912345678",
        text="ya no quiero vivir",
        now=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
    )

    assert result.action == "CRISIS"
    assert result.crisis is True
    assert "No tienes que estar solo" in result.response_text
    assert client.sent[-1].kind == "CRISIS"


def test_handle_inbound_crisis_records_journal_entry(db_conn) -> None:
    db = Database(db_conn)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    service.handle_inbound(
        from_number="+56912345678",
        text="ya no quiero vivir",
        now=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
    )

    recorded = db.crisis_journal.list_recent()
    assert len(recorded) == 1


def test_handle_inbound_allows_when_no_number_paired_yet(db_conn) -> None:
    # Onboarding incompleto (sin whatsapp_number configurado aún) no debe
    # bloquear el flujo — solo se autentica una vez hay un número emparejado.
    db = Database(db_conn)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(from_number="+56999999999", text="memoria")

    assert result.action != "UNAUTHORIZED"


def test_handle_inbound_rejects_message_from_unpaired_number(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)  # empareja +56912345678
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(from_number="+56900000000", text="mis datos")

    assert result.action == "UNAUTHORIZED"


def test_handle_inbound_crisis_response_bypasses_sender_check(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)  # empareja +56912345678
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(
        from_number="+56900000000",
        text="ya no quiero vivir",
        now=datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
    )

    assert result.action == "CRISIS"
    assert result.crisis is True


def test_send_progress_report_uses_real_task_progress(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db, progress=True)
    now = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("leer papers", now - timedelta(hours=1)))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=now)
    client = InMemoryWhatsAppClient()
    service = WhatsAppService(db, client)

    message = service.send_progress_report(to="+56912345678", now=now)

    assert message.kind == "PROGRESS_REPORT"
    assert "completaste 1 tarea" in message.text
    assert "leer papers" not in message.text
    assert "tarea pequeña" in message.text


def test_send_smart_checkin_requires_proactive_consent(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    message = service.send_smart_checkin(to="+56912345678")

    assert message.kind == "CONSENT_REQUIRED"


def test_send_smart_checkin_uses_progress_only_with_consent(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive_whatsapp(db, progress=False)
    now = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("estudiar ramo privado", now))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=now)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    message = service.send_smart_checkin(to="+56912345678", now=now)

    assert message.kind == "SMART_CHECKIN"
    assert message.metadata["recommendation"] == "PLANNING_NUDGE"
    assert "completaste" not in message.text
    assert "estudiar ramo privado" not in message.text


def test_send_smart_checkin_can_send_private_safe_progress(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive_whatsapp(db, progress=True)
    now = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("preparar prueba secreta", now))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=now)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    message = service.send_smart_checkin(to="+56912345678", now=now)

    assert message.kind == "SMART_CHECKIN"
    assert message.metadata["recommendation"] == "PROGRESS_CELEBRATION"
    assert "completaste 1 tarea" in message.text
    assert "preparar prueba secreta" not in message.text


def test_send_action_menu_offers_clear_choices(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    message = service.send_action_menu(to="+56912345678")

    assert message.kind == "ACTION_MENU"
    assert "1. Elegir una tarea corta" in message.text
    assert "4. Check-in de ánimo" in message.text
    assert "5. Plan rápido" in message.text
    assert "6. Configuración" in message.text


def test_handle_inbound_menu_choice_returns_progress(db_conn) -> None:
    db = Database(db_conn)
    now = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)
    task = db.tasks.create(create_focus_task("programar", now))
    db.tasks.update_status(task.id, TaskStatus.DONE, completed_at=now)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(from_number="+56912345678", text="3", now=now)

    assert result.action == "MENU_PROGRESS"
    assert "programar" not in result.response_text
    assert "completaste 1 tarea" in result.response_text


def test_handle_inbound_menu_choice_returns_privacy_safe_study_plan(db_conn) -> None:
    db = Database(db_conn)
    db.tasks.create(
        create_focus_task("preparar prueba privada", datetime(2026, 6, 10, 16, 0, tzinfo=UTC))
    )
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(
        from_number="+56912345678",
        text="5",
        now=datetime(2026, 6, 10, 16, 0, tzinfo=UTC),
    )

    assert result.action == "MENU_PLAN"
    assert "Bloque sugerido" in result.response_text
    assert "preparar prueba privada" not in result.response_text


def test_handle_inbound_menu_focus_keeps_pending_duration(db_conn) -> None:
    db = Database(db_conn)
    service = WhatsAppService(db, InMemoryWhatsAppClient())
    now = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)

    prompt = service.handle_inbound(from_number="+56912345678", text="2", now=now)
    minutes = service.handle_inbound(from_number="+56912345678", text="25", now=now)
    focus = service.handle_inbound(
        from_number="+56912345678",
        text="estudiar cálculo",
        now=now,
    )

    assert prompt.action == "MENU_FOCUS"
    assert minutes.action == "MENU_FOCUS"
    assert "Qué actividad" in minutes.response_text
    assert focus.action == "FOCUS"
    assert focus.focus_session_id is not None
    assert "25 minutos para cálculo" in focus.response_text


def test_handle_inbound_menu_focus_keeps_pending_title(db_conn) -> None:
    db = Database(db_conn)
    service = WhatsAppService(db, InMemoryWhatsAppClient())
    now = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)

    service.handle_inbound(from_number="+56912345678", text="2", now=now)
    title = service.handle_inbound(
        from_number="+56912345678",
        text="estudiar química",
        now=now,
    )
    focus = service.handle_inbound(from_number="+56912345678", text="30 minutos", now=now)

    assert title.action == "MENU_FOCUS"
    assert "Por cuántos minutos" in title.response_text
    assert focus.action == "FOCUS"
    assert "30 minutos para química" in focus.response_text


def test_handle_inbound_menu_mood_guides_next_reply(db_conn) -> None:
    db = Database(db_conn)
    service = WhatsAppService(db, InMemoryWhatsAppClient())
    now = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)

    service.handle_inbound(from_number="+56912345678", text="4", now=now)
    unclear = service.handle_inbound(from_number="+56912345678", text="meh", now=now)
    mood = service.handle_inbound(from_number="+56912345678", text="bajo", now=now)

    assert unclear.action == "MENU_MOOD"
    assert "bien, normal o bajo" in unclear.response_text
    assert mood.action == "MOOD_RECORDED"
    assert mood.stored_mood == "low"


def test_handle_inbound_can_pause_and_resume_proactive_messages(db_conn) -> None:
    db = Database(db_conn)
    _enable_proactive_whatsapp(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    paused = service.handle_inbound(from_number="+56912345678", text="pausar mensajes")
    paused_message = service.send_smart_checkin(to="+56912345678")
    resumed = service.handle_inbound(from_number="+56912345678", text="reanudar mensajes")

    assert paused.action == "MESSAGES_PAUSED"
    assert paused_message.kind == "CONSENT_REQUIRED"
    assert resumed.action == "MESSAGES_RESUMED"
    assert UserConfigService(db).proactive_messages_can_send() is True


def test_handle_inbound_shows_config_and_user_data_export(db_conn) -> None:
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_profile({"preferred_name": "Nico", "university": "UDD"})
    config.update_channels({"wifi_ssid": "Casa", "whatsapp_number": "+56912345678"})
    config.update_consent({"whatsapp_enabled": True})
    config.add_memory(text="Prefiero bloques cortos")
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    status = service.handle_inbound(from_number="+56912345678", text="configuración")
    exported = service.handle_inbound(from_number="+56912345678", text="exportar mis datos")

    assert status.action == "CONFIG_STATUS"
    assert "WhatsApp: sí" in status.response_text
    assert "Memorias guardadas: 1" in status.response_text
    assert exported.action == "USER_DATA_EXPORT"
    assert "Nombre: Nico" in exported.response_text
    assert "WiFi guardado: Casa" in exported.response_text


def test_handle_inbound_deletes_user_data_only_after_confirmation(db_conn) -> None:
    db = Database(db_conn)
    config = UserConfigService(db)
    config.update_profile({"preferred_name": "Nico"})
    config.update_channels({"wifi_ssid": "Casa"})
    config.update_consent({"whatsapp_enabled": True})
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    prompt = service.handle_inbound(from_number="+56912345678", text="borrar mis datos")
    rejected = service.handle_inbound(from_number="+56912345678", text="no", now=None)
    confirmed = service.handle_inbound(
        from_number="+56912345678",
        text="confirmar borrar mis datos",
    )

    assert prompt.action == "DELETE_USER_DATA_CONFIRM"
    assert rejected.action == "DELETE_USER_DATA_CONFIRM"
    assert confirmed.action == "USER_DATA_DELETED"
    assert UserConfigService(db).get_profile().preferred_name is None


# ---------------------------------------------------------------------------
# Triage por WhatsApp — derivación a bienestar y redirección clínica
# ---------------------------------------------------------------------------


def test_inbound_personal_disclosure_gets_wellbeing_referral(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    UserConfigService(db).update_channels(
        {"wellbeing_unit_name": "Bienestar UDD", "wellbeing_unit_phone": "+56228203419"}
    )
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(
        from_number="+56912345678", text="necesito un psicólogo pero no sé cómo partir"
    )

    assert result.action == "WELLBEING_REFERRAL"
    assert "Bienestar UDD" in result.response_text  # nombra la unidad
    assert "+56228203419" not in result.response_text  # sin recitar el número
    assert result.crisis is False


def test_inbound_referral_without_configured_unit_still_orients(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(
        from_number="+56912345678", text="me diagnosticaron depresión el año pasado"
    )

    assert result.action == "WELLBEING_REFERRAL"
    assert result.response_text.strip()


def test_inbound_clinical_question_is_redirected(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(
        from_number="+56912345678", text="¿qué medicamento debería tomar para la ansiedad?"
    )

    assert result.action == "SCOPE_REDIRECT"


def test_inbound_crisis_still_wins_over_triage(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(
        from_number="+56912345678", text="necesito un psicólogo, ya no quiero vivir"
    )

    assert result.action == "CRISIS"
    assert result.crisis is True


def test_inbound_unpaired_number_does_not_get_referral(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)  # empareja +56912345678
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(from_number="+56900000000", text="necesito un psicólogo")

    assert result.action == "UNAUTHORIZED"


def test_inbound_mood_words_still_record_mood_not_referral(db_conn) -> None:
    db = Database(db_conn)
    _enable_whatsapp(db)
    service = WhatsAppService(db, InMemoryWhatsAppClient())

    result = service.handle_inbound(from_number="+56912345678", text="ando bajo hoy")

    assert result.action == "MOOD_RECORDED"
