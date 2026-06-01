"""Prueba directa: sintetiza con el TTS configurado y reproduce por el parlante.

Uso (Pi): PYTHONPATH=src .venv/bin/python scripts/test_tts.py

Selecciona automáticamente ElevenLabs o Google según `TTS_PROVIDER` en .env.
Reproduce por la card 2 (jack 3.5mm) con `mpg123`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bootstrap import _try_real_tts
from config import Settings


def main() -> int:
    settings = Settings()
    tts = _try_real_tts(settings)
    if tts is None:
        print("TTS real no disponible. Revisa credenciales y libs en .env.")
        return 1

    text = "Hola, soy Rako. Es un gusto conocerte."
    print(f"Sintetizando: {text!r}")
    result = tts.synthesize(text)

    out = Path("/tmp/rako-test.mp3")
    out.write_bytes(result.audio.data)
    print(f"Audio escrito en {out} ({len(result.audio.data)} bytes)")

    print("Reproduciendo por el parlante...")
    subprocess.run(
        ["mpg123", "-q", "-o", "alsa", "-a", "plughw:seeed2micvoicec,0", str(out)],
        check=True,
    )
    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
