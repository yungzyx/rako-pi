"""CLI de Rako — entrypoint.

Subcomandos:

  demo-turn TEXT          Procesa un turno con TEXT como input del usuario.
  demo-crisis-panic       Simula presión del botón pánico físico.
  reindex-rag             Re-indexa la vault de Obsidian (TODO completo).
  purge-all               Borra TODO el historial e identidad del usuario.

Uso (mac/dev):
  PYTHONPATH=src python -m main demo-turn "me siento atascado"
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from bootstrap import Application, build_dev_application, build_pi_application
from channels.whatsapp.client import InMemoryWhatsAppClient
from channels.whatsapp.scheduler import (
    SmartCheckinSchedule,
    decide_smart_checkin,
    send_due_smart_checkin,
)
from channels.whatsapp.service import WhatsAppService
from config import Settings
from orchestrator.orchestrator import TurnInput, TurnKind
from orchestrator.types import default_user_context
from product.user_config import UserConfigService
from productivity.coaching import build_coaching_recommendation
from safety.types import PanicSource


def _select_builder(settings: Settings) -> Callable[[Settings], Application]:
    """Elige el factory según el entorno: prod → Pi (hardware real),
    dev/staging → dev (fakes). El factory de Pi cae a fakes silenciosamente
    si las libs no están disponibles, así que llamarlo en mac/CI no rompe."""
    if settings.rako_env == "prod":
        return build_pi_application
    return build_dev_application


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rako", description="Rako — CLI del cerebro.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo-turn", help="Procesa un turno con texto.")
    p_demo.add_argument("text", help="Texto del usuario.")

    sub.add_parser("demo-crisis-panic", help="Simula el botón pánico físico.")

    sub.add_parser("reindex-rag", help="Re-indexa la vault Obsidian (TODO).")

    sub.add_parser("purge-all", help="Borra todo el historial e identidad.")

    p_run = sub.add_parser("run", help="Loop principal continuo (Ctrl+C para detener).")
    p_run.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Límite de iteraciones (default: infinito).",
    )

    p_checkin = sub.add_parser(
        "smart-checkin",
        help="Evalúa y dispara un smart check-in WhatsApp si corresponde.",
    )
    p_checkin.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra la decisión y el mensaje sugerido; no registra envío.",
    )
    p_checkin.add_argument(
        "--at",
        default=None,
        help="Fecha/hora ISO para pruebas, por ejemplo 2026-06-20T14:00:00+00:00.",
    )
    p_checkin.add_argument("--min-interval-hours", type=float, default=6.0)
    p_checkin.add_argument("--quiet-start-hour", type=int, default=22)
    p_checkin.add_argument("--quiet-end-hour", type=int, default=8)
    p_checkin.add_argument("--recent-interaction-minutes", type=float, default=45.0)

    args = parser.parse_args(argv)

    settings = Settings()
    builder = _select_builder(settings)
    app = builder(settings)
    try:
        if args.cmd == "demo-turn":
            return _run_demo_turn(app, args.text)
        if args.cmd == "demo-crisis-panic":
            return _run_demo_crisis_panic(app)
        if args.cmd == "reindex-rag":
            return _run_reindex_rag(app)
        if args.cmd == "purge-all":
            return _run_purge_all(app)
        if args.cmd == "run":
            return _run_loop(app, max_iterations=args.max_iterations)
        if args.cmd == "smart-checkin":
            return _run_smart_checkin(
                app,
                dry_run=args.dry_run,
                at=args.at,
                min_interval_hours=args.min_interval_hours,
                quiet_start_hour=args.quiet_start_hour,
                quiet_end_hour=args.quiet_end_hour,
                recent_interaction_minutes=args.recent_interaction_minutes,
            )
        parser.error(f"unknown command: {args.cmd}")  # pragma: no cover
        return 2  # pragma: no cover - argparse already exits
    finally:
        app.close()


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------


def _run_demo_turn(app: Application, text: str) -> int:
    now = datetime.now(UTC)
    turn = TurnInput(
        transcript=text,
        emotion=None,
        panic_button=None,
        emotion_history=(),
        last_high_distress_at=None,
        last_interaction_at=None,
        user_context=default_user_context(now),
        now=now,
    )
    result = app.orchestrator.handle_turn(turn)

    print(f"[Rako] {result.text}")
    print()
    print(f"  kind={result.kind.value}")
    if result.rag_chunk_ids:  # pragma: no cover - requires real RAG
        print(f"  rag_chunks={list(result.rag_chunk_ids)}")
    if result.metadata:
        print(f"  metadata={dict(result.metadata)}")
    return 0


def _run_demo_crisis_panic(app: Application) -> int:
    now = datetime.now(UTC)
    turn = TurnInput(
        transcript="",
        emotion=None,
        panic_button=PanicSource.PHYSICAL,
        emotion_history=(),
        last_high_distress_at=None,
        last_interaction_at=None,
        user_context=default_user_context(now),
        now=now,
    )
    result = app.orchestrator.handle_turn(turn)

    print(f"[Rako] {result.text}")
    print()
    print(f"  kind={result.kind.value}")
    print(f"  notify_contact={result.notify_contact}")
    print(f"  show_resources={result.show_resources}")
    if result.metadata:
        print(f"  metadata={dict(result.metadata)}")
    if result.kind is TurnKind.CRISIS_PROTOCOL:
        print()
        print("  protocolo de crisis ejecutado.")
    return 0


def _run_reindex_rag(app: Application) -> int:
    from rag.indexer import index_vault

    settings = app.settings
    result = index_vault(
        vault_path=settings.obsidian_vault_path,
        db_path=settings.chroma_db_path,
        collection_name=settings.chroma_collection,
    )
    print(
        f"OK: indexados {result.indexed_count} chunks en colección "
        f"'{result.collection_name}' desde {settings.obsidian_vault_path}."
    )
    return 0


def _run_purge_all(app: Application) -> int:
    app.db.purge_all_user_data()
    print("OK: historial e identidad del usuario purgados.")
    return 0


def _run_loop(app: Application, *, max_iterations: int | None) -> int:
    from orchestrator.run import RunLoop

    loop = RunLoop(app=app)
    print("[Rako] loop principal iniciado. Ctrl+C para detener.")
    try:
        loop.run(max_iterations=max_iterations)
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("\n[Rako] deteniendo.")
    return 0


def _run_smart_checkin(
    app: Application,
    *,
    dry_run: bool,
    at: str | None,
    min_interval_hours: float,
    quiet_start_hour: int,
    quiet_end_hour: int,
    recent_interaction_minutes: float,
) -> int:
    now = _parse_cli_datetime(at)
    schedule = SmartCheckinSchedule(
        min_interval=timedelta(hours=min_interval_hours),
        quiet_start_hour=quiet_start_hour,
        quiet_end_hour=quiet_end_hour,
        recent_interaction_window=timedelta(minutes=recent_interaction_minutes),
    )
    decision = decide_smart_checkin(app.db, now=now, schedule=schedule)
    print(f"[Rako] smart-checkin decision={decision.reason} send={decision.should_send}")
    if decision.to:
        print(f"  to={decision.to}")
    if not decision.should_send:
        return 0

    if dry_run:
        config = UserConfigService(app.db)
        recommendation = build_coaching_recommendation(
            app.db,
            now=now,
            include_progress=config.progress_reports_can_send(),
        )
        print(f"  recommendation={recommendation.kind}")
        print(f"  text={recommendation.text}")
        return 0

    client = InMemoryWhatsAppClient()
    service = WhatsAppService(app.db, client)
    message = send_due_smart_checkin(service, app.db, now=now, schedule=schedule)
    if message is None:
        print("  no enviado")
        return 0
    print(f"  sent_kind={message.kind}")
    print(f"  text={message.text}")
    return 0


def _parse_cli_datetime(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
