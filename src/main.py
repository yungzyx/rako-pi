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
from datetime import UTC, datetime

from bootstrap import Application, build_dev_application, build_pi_application
from config import Settings
from orchestrator.orchestrator import TurnInput, TurnKind
from orchestrator.types import default_user_context
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


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
