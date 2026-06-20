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
from orchestrator.context import build_user_context
from orchestrator.memory import ConversationMemory
from orchestrator.orchestrator import TurnInput


def main() -> int:
    settings = Settings()
    app = build_pi_application(settings)
    memory = ConversationMemory()
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
            turn_in = TurnInput(
                transcript=text,
                emotion=None,
                panic_button=None,
                emotion_history=(),
                last_high_distress_at=None,
                last_interaction_at=None,
                user_context=build_user_context(
                    app.db,
                    now,
                    recent_conversation=memory.lines(),
                ),
                now=now,
            )
            result = app.orchestrator.handle_turn(turn_in)
            print(f"Rako: {result.text}")
            memory.add_turn(user=text, rako=result.text)

            audio = app.tts.synthesize(result.text)
            out = Path("/tmp/rako-reply.mp3")
            out.write_bytes(audio.audio.data)
            subprocess.run(
                ["mpg123", "-q", "-o", "alsa", "-a", "plughw:seeed2micvoicec,0", str(out)],
                check=False,
            )
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
