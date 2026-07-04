#!/usr/bin/env python3
"""Pre-sintetiza las frases curadas de Rako para uso offline.

Corre en la Pi con credenciales/red disponibles. Sintetiza cada frase
curada (protocolo de crisis, derivaciones, fallbacks) con el TTS real
configurado y la guarda en el cache local (`TTS_CACHE_DIR`). Después, la
cadena de TTS puede hablar esas frases sin internet — el protocolo de
crisis deja de depender de que un proveedor cloud responda.

Uso:
    ./scripts/rako-pregen-tts            # sintetiza lo que falte
    ./scripts/rako-pregen-tts --force    # re-sintetiza todo
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from bootstrap import _try_elevenlabs_tts, _try_google_tts
from config import Settings
from orchestrator.orchestrator import _LLM_FALLBACK_TEXT
from product.user_config import UserConfigService
from safety.responses import all_response_texts
from safety.scope import (
    build_elevated_support_response,
    build_scope_redirect_response,
    build_wellbeing_referral_response,
)
from voice.tts_cache import PrerecordedTTS

# Frases operativas fijas que también deben poder sonar sin red.
# El texto "no te escuché" debe coincidir con _DID_NOT_HEAR_TEXT de
# scripts/button_conversation.py (no importable: scripts no es paquete).
_OPERATIONAL_TEXTS = (
    "No te escuché bien. ¿Me lo repites?",
    _LLM_FALLBACK_TEXT,
)


def _curated_texts(settings: Settings) -> tuple[str, ...]:
    texts: list[str] = list(all_response_texts())
    texts.append(build_scope_redirect_response())
    texts.append(build_elevated_support_response())
    # La derivación a bienestar depende de la unidad configurada en ESTA
    # placa; si cambia la configuración, correr este script de nuevo.
    from db.database import Database

    db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
    try:
        channels = UserConfigService(db).get_channels()
    finally:
        db.close()
    texts.append(
        build_wellbeing_referral_response(
            unit_name=channels.wellbeing_unit_name,
            unit_phone=channels.wellbeing_unit_phone,
        )
    )
    texts.extend(_OPERATIONAL_TEXTS)
    # Dedup preservando orden.
    seen: set[str] = set()
    unique = [text for text in texts if not (text in seen or seen.add(text))]
    return tuple(unique)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-sintetizar frases curadas de Rako")
    parser.add_argument("--force", action="store_true", help="Re-sintetizar aunque ya existan")
    args = parser.parse_args(argv)

    settings = Settings()
    tts = _try_elevenlabs_tts(settings) or _try_google_tts(settings)
    if tts is None:
        print("ERROR: no hay TTS real configurado (ElevenLabs/Google). Revisa .env.")
        return 1

    cache = PrerecordedTTS(Path(settings.tts_cache_dir))
    texts = _curated_texts(settings)
    synthesized = 0
    skipped = 0
    for text in texts:
        if not args.force and cache.has(text):
            skipped += 1
            continue
        result = tts.synthesize(text)
        path = cache.store(text, result)
        synthesized += 1
        print(f"  ✓ {path.name}  ({len(text)} chars, voz {result.voice_name})")

    print(f"\nListo: {synthesized} sintetizadas, {skipped} ya estaban en cache.")
    print(f"Cache: {settings.tts_cache_dir} ({cache.entry_count()} frases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
