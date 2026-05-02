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
from datetime import datetime, timezone

from bootstrap import Application, build_dev_application
from config import Settings
from orchestrator.orchestrator import TurnInput, TurnKind
from orchestrator.types import UserContext
from safety.types import PanicSource


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rako", description="Rako — CLI del cerebro.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo-turn", help="Procesa un turno con texto.")
    p_demo.add_argument("text", help="Texto del usuario.")

    sub.add_parser("demo-crisis-panic", help="Simula el botón pánico físico.")

    sub.add_parser("reindex-rag", help="Re-indexa la vault Obsidian (TODO).")

    sub.add_parser("purge-all", help="Borra todo el historial e identidad.")

    args = parser.parse_args(argv)

    settings = Settings()
    app = build_dev_application(settings)
    try:
        if args.cmd == "demo-turn":
            return _run_demo_turn(app, args.text)
        if args.cmd == "demo-crisis-panic":
            return _run_demo_crisis_panic(app)
        if args.cmd == "reindex-rag":
            return _run_reindex_rag(app)
        if args.cmd == "purge-all":
            return _run_purge_all(app)
        parser.error(f"unknown command: {args.cmd}")  # pragma: no cover
        return 2  # pragma: no cover - argparse already exits
    finally:
        app.close()


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------


def _run_demo_turn(app: Application, text: str) -> int:
    now = datetime.now(timezone.utc)
    turn = TurnInput(
        transcript=text,
        emotion=None,
        panic_button=None,
        emotion_history=(),
        last_high_distress_at=None,
        last_interaction_at=None,
        user_context=_default_context(now),
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
    now = datetime.now(timezone.utc)
    turn = TurnInput(
        transcript="",
        emotion=None,
        panic_button=PanicSource.PHYSICAL,
        emotion_history=(),
        last_high_distress_at=None,
        last_interaction_at=None,
        user_context=_default_context(now),
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
    print(
        "TODO: reindex con sentence-transformers + ChromaDB cuando se "
        "instalen las deps en la Pi. Por ahora, "
        "`python scripts/reindex_rag.py` queda como stub."
    )
    return 0


def _run_purge_all(app: Application) -> int:
    app.db.purge_all_user_data()
    print("OK: historial e identidad del usuario purgados.")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_context(now: datetime) -> UserContext:
    hour = now.hour
    if 6 <= hour < 12:
        tod = "mañana"
    elif 12 <= hour < 19:
        tod = "tarde"
    else:
        tod = "noche"
    return UserContext(
        pending_task_count=0,
        recent_completion_count=0,
        robot_level=1,
        time_of_day=tod,
        recent_mood_summary=None,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
