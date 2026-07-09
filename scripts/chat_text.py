"""Chat por texto — escribes en consola, Rako responde y lo dice por el parlante.

Uso (Pi): PYTHONPATH=src .venv/bin/python scripts/chat_text.py
Salir:    Ctrl+C o Ctrl+D

Requiere `OPENAI_API_KEY` o `ANTHROPIC_API_KEY` en `.env`. Sin key, la
respuesta viene de un cliente canned (no es chatbot real).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from bootstrap import build_pi_application
from config import Settings
from orchestrator.turn_session import TurnSession


def main() -> int:
    settings = Settings()
    app = build_pi_application(settings)
    # Mismo pipeline que el loop de voz/botón (TurnSession): memoria con
    # restauración, triage, señales de aftercare/inactividad y persistencia con
    # gate de privacidad. Antes este canal armaba su propio TurnInput "pelado"
    # y quedaba SIN aftercare post-crisis ni triage de recurrencia.
    session = TurnSession(db=app.db, settings=app.settings)
    session.restore_recent_memory()
    print("Rako listo. Escribe algo y Enter. Ctrl+C para salir.")
    try:
        while True:
            try:
                text = input("> ").strip()
            except EOFError:
                break
            if not text:
                continue

            now = datetime.now(UTC)
            turn_in = session.build_turn_input(text, now=now)
            result = app.orchestrator.handle_turn(turn_in)
            print(f"Rako: {result.text}")
            session.complete_turn(transcript=text, result=result, now=now)

            try:
                audio = app.tts.synthesize(result.text)
                out = Path("/tmp/rako-reply.mp3")
                out.write_bytes(audio.audio.data)
                subprocess.run(
                    ["mpg123", "-q", "-o", "alsa", "-a", "plughw:seeed2micvoicec,0", str(out)],
                    check=False,
                )
            except Exception as exc:
                # La voz es opcional en este canal: el texto ya se imprimió.
                print(f"No pude sintetizar voz: {exc}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
