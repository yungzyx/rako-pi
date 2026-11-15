# Arquitectura de Rako

[Volver al proyecto](../README.md) · [Índice de documentación](README.md)

Los comandos se ejecutan desde la raíz del repositorio.

## Arquitectura

Pipeline de un turno de voz (objetivo 3–5 s):

```
botón/mic → STT cloud → seguridad (crisis → bypass total del LLM)
         → triage (derivación bienestar / tono / normal)
         → orquestador (RAG + estado SQLite cifrado)
         → LLM → TTS cloud → parlante + ojos OLED + SQLite
```

Servicios cloud reales (configurables por `.env`):

| Rol | Primario | Fallback |
| --- | --- | --- |
| LLM | OpenAI `gpt-4o-mini` | Anthropic Claude |
| STT | Google Cloud Speech | OpenAI Whisper (opción) |
| TTS | ElevenLabs | Google Cloud TTS |
| Mensajería | WhatsApp Business Cloud API (Meta) | — |
| Backend | Firebase (diseñado, **no conectado aún** — cliente fake) | — |

En crisis el LLM se **bypassea por completo**: solo respuestas pre-curadas
por profesionales, recursos de ayuda configurados y registro privado local. El análisis de emoción local (SER) está
diferido — hoy no corre en el dispositivo.

```
src/
├── voice/          STT, TTS, wake-word
├── emotion/        análisis de patrones (SER local diferido)
├── orchestrator/   decisión central, prompts, RunLoop, memoria conversacional
├── rag/            ChromaDB + indexer + embeddings
├── hardware/       GPIO: LEDs, botones, OLED, audio I/O
├── db/             SQLite + SQLCipher (estado del usuario, nunca sale de la Pi)
├── sync/           cliente Firebase (sanitizer + allowlist; backend pendiente)
├── safety/         detector de crisis, triage graduado, protocolo (bypass LLM)
├── channels/       canal WhatsApp Business Cloud API
├── mobile/         API FastAPI local + páginas de setup/factory
├── product/        provisioning, factory, OTA, fleet, auditoría de seguridad
└── productivity/   foco, coaching, mindfulness, progreso
```

## RAG

```bash
python scripts/reindex_rag.py
```

Lee la vault de Obsidian (`OBSIDIAN_VAULT_PATH`, default `../Rako-kb`) y
reescribe la colección de ChromaDB en `CHROMA_DB_PATH`. Curaduría del
contenido: `../docs/RAG_PROMPT.md`.

## Privacidad — lectura obligatoria antes de tocar el código

- **Datos emocionales detallados nunca salen de la Pi** (SQLite local
  cifrado con SQLCipher).
- **Audio del usuario nunca se persiste** — ni en disco ni en cloud.
- **El LLM se bypassea en crisis.** Solo respuestas curadas por
  profesionales; el sistema nunca diagnostica y siempre deriva.
- **Borrado total** desde la app o WhatsApp purga todo el historial local
  con efecto inmediato.
- **Modo no-grabación** (`RAKO_MODE=private`): el robot opera sin guardar
  historial de interacciones.

Reglas completas y qué puede salir hacia cada API cloud:
[`CLAUDE.md`](../CLAUDE.md) §4.
