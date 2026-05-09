"""Chat por texto — escribes en consola, Rako responde y lo dice por el parlante.

Uso (Pi): PYTHONPATH=src .venv/bin/python scripts/chat_text.py
Salir:    Ctrl+C o Ctrl+D

Requiere `OPENAI_API_KEY` o `ANTHROPIC_API_KEY` en `.env`. Sin key, la
respuesta viene de un cliente canned (no es chatbot real).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bootstrap import build_pi_application
from config import Settings
from orchestrator.orchestrator import TurnInput
from orchestrator.types import default_user_context


def main() -> int:
    settings = Settings()
    app = build_pi_application(settings)
    print("Rako listo. Escribe algo y Enter. Ctrl+C para salir.")
    try:
        while True:
            try:
                text = input("> ").strip()
            except EOFError:
                break
            if not text:
                continue

            now = datetime.now(timezone.utc)
            turn_in = TurnInput(
                transcript=text,
                emotion=None,
                panic_button=None,
                emotion_history=(),
                last_high_distress_at=None,
                last_interaction_at=None,
                user_context=default_user_context(now),
                now=now,
            )
            result = app.orchestrator.handle_turn(turn_in)
            print(f"Rako: {result.text}")

            audio = app.tts.synthesize(result.text)
            out = Path("/tmp/rako-reply.mp3")
            out.write_bytes(audio.audio.data)
            subprocess.run(["mpg123", "-q", "-a", "hw:2,0", str(out)], check=False)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
