"""Módulo de voz.

Captura audio del micrófono, detecta wake-words y media entre el usuario y
las APIs de voz cloud (Google STT/TTS, fallback Whisper local).

Responsabilidades:
- Captura continua de audio con buffer circular (sin persistir).
- Detección de wake-word ("Hey Rako", "Hola Rako", "Oye Rako").
- Cliente STT que envía audio a Google Cloud Speech y devuelve texto.
- Cliente TTS que sintetiza texto con voz neuronal en español chileno.
- Fallback offline con whisper.cpp (stt_local) + frases pre-generadas (tts_cache).

Restricción crítica: el audio del usuario NUNCA se persiste a disco.
Solo vive en buffers en memoria mientras dura la captura.
"""
