"""Detección proactiva de bloqueo — decisión determinística y auditable.

El corazón del producto: notar evasión (tareas pendientes + silencio
largo) y ofrecer un empujón suave por voz, sin culpa y sin insistir.
Este módulo solo DECIDE; el despacho (voz/LEDs) vive en el CLI
(`rako.sh proactive-check`) o en el timer de systemd opcional.

Salvaguardas, en orden:
1. Modo privado: sin historial persistido no hay señal — apagado.
2. Crisis reciente: nunca competir con el protocolo de seguridad.
3. Horario silencioso del usuario (do_not_disturb, en SU zona horaria).
4. Rate limit: intervalo mínimo entre nudges y tope diario.
5. Señal real: tareas pendientes + inactividad prolongada de un usuario
   que sí venía usando el dispositivo (nunca molesta a un Rako recién
   provisionado que no se ha usado).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from db.database import Database
from orchestrator.context import find_last_interaction_at
from product.user_config import UserConfigService
from productivity.crisis_gate import has_recent_crisis_event

_LAST_NUDGE_KEY = "proactive.last_nudge"
DEFAULT_MIN_INTERVAL_HOURS = 4.0
DEFAULT_INACTIVITY_HOURS = 3.0
DEFAULT_MAX_PER_DAY = 2

_NUDGE_TEXT = (
    "Oye, ¿probamos solo cinco minutos con lo que tienes pendiente? "
    "Partir chico cuenta igual. Yo te acompaño."
)


@dataclass(frozen=True, slots=True)
class ProactiveDecision:
    should_nudge: bool
    reason: str
    nudge_text: str | None = None


def decide_proactive_nudge(
    db: Database,
    *,
    now: datetime,
    rako_mode: str,
    do_not_disturb_start: str,
    do_not_disturb_end: str,
    min_interval_hours: float = DEFAULT_MIN_INTERVAL_HOURS,
    inactivity_hours: float = DEFAULT_INACTIVITY_HOURS,
    max_per_day: int = DEFAULT_MAX_PER_DAY,
) -> ProactiveDecision:
    if rako_mode == "private":
        return ProactiveDecision(False, "private_mode")
    if has_recent_crisis_event(db, now=now):
        return ProactiveDecision(False, "recent_crisis")
    if _in_quiet_hours(db, now=now, start=do_not_disturb_start, end=do_not_disturb_end):
        return ProactiveDecision(False, "quiet_hours")

    rate_block = _rate_limit_reason(
        db, now=now, min_interval_hours=min_interval_hours, max_per_day=max_per_day
    )
    if rate_block is not None:
        return ProactiveDecision(False, rate_block)

    if not db.tasks.list_pending():
        return ProactiveDecision(False, "no_pending_tasks")
    last_interaction = find_last_interaction_at(db)
    if last_interaction is None:
        # Dispositivo sin uso todavía: un nudge aquí sería spam, no apoyo.
        return ProactiveDecision(False, "never_used")
    if now - last_interaction < timedelta(hours=inactivity_hours):
        return ProactiveDecision(False, "recently_active")

    return ProactiveDecision(True, "pending_without_activity", nudge_text=_NUDGE_TEXT)


def record_nudge(db: Database, *, now: datetime) -> None:
    """Registra el nudge despachado para el rate limit (no guarda contenido)."""
    previous = _read_nudge_state(db)
    same_day = previous.get("date") == now.date().isoformat()
    count_today = int(previous.get("count_today", 0)) + 1 if same_day else 1
    db.config.set(
        _LAST_NUDGE_KEY,
        json.dumps(
            {"at": now.isoformat(), "date": now.date().isoformat(), "count_today": count_today},
            ensure_ascii=False,
        ),
    )


def _rate_limit_reason(
    db: Database, *, now: datetime, min_interval_hours: float, max_per_day: int
) -> str | None:
    state = _read_nudge_state(db)
    raw_at = state.get("at")
    if isinstance(raw_at, str):
        last_at = datetime.fromisoformat(raw_at)
        if now - last_at < timedelta(hours=min_interval_hours):
            return "too_soon"
    if state.get("date") == now.date().isoformat() and (
        int(state.get("count_today", 0)) >= max_per_day
    ):
        return "daily_cap"
    return None


def _read_nudge_state(db: Database) -> dict[str, object]:
    raw = db.config.get(_LAST_NUDGE_KEY)
    if raw is None:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _in_quiet_hours(db: Database, *, now: datetime, start: str, end: str) -> bool:
    timezone = UserConfigService(db).get_profile().timezone
    try:
        local = now.astimezone(ZoneInfo(timezone))
    except (KeyError, ValueError):
        local = now
    start_minutes = _parse_hhmm(start)
    end_minutes = _parse_hhmm(end)
    current = local.hour * 60 + local.minute
    if start_minutes <= end_minutes:
        return start_minutes <= current < end_minutes
    # Ventana que cruza medianoche (22:00 → 08:00).
    return current >= start_minutes or current < end_minutes


def _parse_hhmm(value: str) -> int:
    hours, _, minutes = value.partition(":")
    return int(hours) * 60 + int(minutes or 0)
