"""Build privacy-safe user context for LLM turns."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from db.database import Database
from db.types import TaskStatus
from orchestrator.types import UserContext, default_user_context
from product.user_config import UserConfigService


def build_user_context(
    db: Database,
    now: datetime,
    *,
    recent_conversation: Iterable[str] = (),
    conversation_turns: Iterable[tuple[str, str]] = (),
) -> UserContext:
    """Return aggregate context plus user-controlled non-sensitive memory.

    The LLM gets counts and normal preference memory only. Sensitive memory and
    full transcripts stay local. `conversation_turns` carries the same recent
    history as `recent_conversation`, as (user, rako) pairs for real multi-turn
    messages (both come from ConversationMemory, already 180-char truncated).
    """
    base = default_user_context(now, recent_conversation=recent_conversation)
    tasks = db.tasks.list_recent(limit=100)
    pending = db.tasks.list_pending()
    recent_cutoff = now - timedelta(days=7)
    recent_completed = [
        task
        for task in tasks
        if task.status is TaskStatus.DONE
        and task.completed_at is not None
        and task.completed_at >= recent_cutoff
    ]
    return UserContext(
        pending_task_count=len(pending),
        recent_completion_count=len(recent_completed),
        robot_level=_robot_level(db),
        time_of_day=base.time_of_day,
        recent_mood_summary=_recent_mood_summary(db, now),
        recent_conversation=tuple(recent_conversation),
        conversation_turns=tuple(conversation_turns),
        user_memory=_normal_memory_lines(db),
    )


def _normal_memory_lines(db: Database) -> tuple[str, ...]:
    service = UserConfigService(db)
    memories = [
        f"{memory.category}: {memory.text}"
        for memory in service.list_memory()
        if memory.sensitivity == "normal"
    ]
    return tuple(memories[-8:])


def _robot_level(db: Database) -> int:
    achievements = db.achievements.list_all()
    if not achievements:
        return 1
    return max(1, achievements[0].robot_level_after)


_LOW_MOOD_VALENCE_MAX = -0.35
_LOW_MOOD_LOOKBACK_DAYS = 7


def count_recent_low_mood_days(db: Database, now: datetime) -> int:
    """Días distintos con al menos una muestra de ánimo bajo en la semana.

    Alimenta el triage de recurrencia (safety/triage.py). La fuente real
    hoy son los check-ins de WhatsApp autoreportados; queda listo para
    cuando exista SER local.
    """
    samples = db.emotional_states.list_samples_in_window(
        end=now, lookback=timedelta(days=_LOW_MOOD_LOOKBACK_DAYS)
    )
    low_days = {
        sample.at.date() for sample in samples if sample.vector.valence <= _LOW_MOOD_VALENCE_MAX
    }
    return len(low_days)


def _recent_mood_summary(db: Database, now: datetime) -> str | None:
    samples = db.emotional_states.list_samples_in_window(end=now, lookback=timedelta(hours=24))
    if not samples:
        return None
    avg_valence = sum(sample.vector.valence for sample in samples) / len(samples)
    if avg_valence <= -0.35:
        return "bajo o cansado recientemente"
    if avg_valence >= 0.35:
        return "con buen ánimo recientemente"
    return "estable o neutral recientemente"


# ---------------------------------------------------------------------------
# Señales para el trigger de inactividad post-angustia (safety/detector.py).
# Estos helpers son los que "despiertan" el trigger que estuvo dormido:
# calculan los datos vivos que el detector siempre supo evaluar.
# ---------------------------------------------------------------------------

_HIGH_DISTRESS_VALENCE_MAX = -0.7
_HIGH_DISTRESS_LOOKBACK = timedelta(hours=24)
_JOURNAL_SCAN_LIMIT = 10
_FOLLOWUP_REASON = "PROLONGED_INACTIVITY_AFTER_DISTRESS"


def find_last_high_distress_at(db: Database, now: datetime) -> datetime | None:
    """Última señal de alta angustia dentro de la ventana relevante.

    Fuentes: eventos del crisis_journal (cualquier punto de entrada) y
    muestras emocionales con valencia extrema (check-ins). Los eventos
    cuyo ÚNICO motivo es el propio follow-up de inactividad se ignoran —
    si contaran, cada follow-up renovaría la ventana de frescura y el
    seguimiento se repetiría indefinidamente.
    """
    candidates: list[datetime] = []
    for entry in db.crisis_journal.list_recent(limit=_JOURNAL_SCAN_LIMIT):
        if all(reason == _FOLLOWUP_REASON for reason in entry.reasons):
            continue
        candidates.append(_as_aware_utc(entry.detected_at))
    samples = db.emotional_states.list_samples_in_window(end=now, lookback=_HIGH_DISTRESS_LOOKBACK)
    candidates.extend(
        _as_aware_utc(sample.at)
        for sample in samples
        if sample.vector.valence <= _HIGH_DISTRESS_VALENCE_MAX
    )
    if not candidates:
        return None
    return max(candidates)


def find_last_crisis_at(db: Database) -> datetime | None:
    """Timestamp de la última crisis real registrada en el journal.

    Alimenta la ventana de aftercare post-crisis (orchestrator): tras una
    crisis, los turnos de seguimiento no deben volver al LLM ni al coaching
    de productividad. La ventana de frescura la aplica el orquestador; aquí
    solo devolvemos el evento más reciente. Se ignoran los eventos cuyo
    ÚNICO motivo es el follow-up de inactividad —igual que en
    `find_last_high_distress_at`—, para que un seguimiento no perpetúe la
    ventana. El journal se escribe SIEMPRE (también en modo privado: es un
    evento de seguridad, no historial de producto), así que el aftercare
    también protege en `rako_mode=private`.
    """
    candidates: list[datetime] = []
    for entry in db.crisis_journal.list_recent(limit=_JOURNAL_SCAN_LIMIT):
        if all(reason == _FOLLOWUP_REASON for reason in entry.reasons):
            continue
        candidates.append(_as_aware_utc(entry.detected_at))
    if not candidates:
        return None
    return max(candidates)


def find_last_interaction_at(db: Database) -> datetime | None:
    """Timestamp de la última interacción persistida (None en modo privado
    o dispositivo recién provisionado — el trigger queda apagado ahí)."""
    recent = db.interactions.list_recent(limit=1)
    if not recent:
        return None
    return _as_aware_utc(recent[0].timestamp)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
