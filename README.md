# rako-pi

Cerebro de **Rako** sobre Raspberry Pi 4. Acompañamiento emocional para
estudiantes universitarios con patrones de evasión post-trauma.

> Fuente de verdad técnica: [`../docs/Arquitectura_Tecnica.md`](../docs/Arquitectura_Tecnica.md).
> Brief para Claude / agentes: [`CLAUDE.md`](./CLAUDE.md).

Este repo es **solo el cerebro** sobre la Pi. La app móvil vive en
`../rako-app` (Flutter). El contenido del RAG vive en `../Rako-kb` (vault
Obsidian). Los servicios cloud (Anthropic, Google Speech, Firebase) son
externos.

---

## Arquitectura en una línea

`mic → SER local → STT cloud → orquestador (RAG + SQLite) → Claude → TTS cloud
→ parlante + LEDs + SQLite + sync Firebase`. Detalle completo en el
[doc de arquitectura](../docs/Arquitectura_Tecnica.md).

```
src/
├── voice/         STT, TTS, wake-word
├── emotion/       SER local + análisis de patrones
├── orchestrator/  decisión central + prompts
├── rag/           ChromaDB + indexer + embeddings
├── hardware/      GPIO: LEDs, servos, sensores, botones, audio
├── db/            SQLite + SQLCipher
├── sync/          cliente Firebase (solo metadatos)
└── safety/        detección y protocolo de crisis (bypass LLM)
```

---

## Setup

### Desarrollo local (mac / linux, sin Pi)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# rellenar las credenciales (Anthropic, Google, Firebase) y la clave de cifrado:
#   openssl rand -hex 32
```

> En mac, `RPi.GPIO` y `adafruit-*` se saltan automáticamente por el marker de
> arquitectura. Hardware se mockea. SQLCipher requiere instalar `sqlcipher`
> aparte (`brew install sqlcipher` en macOS).

### Sobre la Raspberry Pi 4

```bash
sudo apt update && sudo apt install -y \
  python3.12 python3.12-venv python3-pip \
  sqlcipher libsqlcipher-dev \
  portaudio19-dev libsndfile1 \
  ffmpeg

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Provisionar GPIO, audio I/O y servicios cloud según `.env.example`.
`scripts/setup_pi.sh` (vacío) consolidará el flujo cuando arranque la
implementación.

---

## Tests

```bash
pytest                                        # toda la suite (mocks de hardware)
pytest tests/test_safety.py -v                # protocolo de crisis (CRÍTICO)
pytest -m "not hardware"                      # excluir tests que necesitan Pi
pytest --cov=src --cov-report=term-missing    # cobertura
```

Cobertura objetivo: **≥ 80%** en módulos no-hardware. El detector de crisis
tiene fixtures dedicados y no puede regresionar.

---

## Re-indexar el RAG desde Obsidian

```bash
python scripts/reindex_rag.py
```

Lee la vault en `OBSIDIAN_VAULT_PATH` (default `../Rako-kb`), genera
embeddings con `paraphrase-multilingual-MiniLM-L12-v2` y reescribe la
colección de ChromaDB en `CHROMA_DB_PATH`.

---

## Privacidad — lectura obligatoria antes de tocar el código

- **Datos emocionales detallados nunca salen de la Pi.**
- **Audio del usuario nunca se persiste.**
- **El LLM se bypassea en crisis.** Respuestas curadas únicamente.
- **Borrado total** desde la app borra SQLite local con efecto inmediato.
- **Modo no-grabación** debe operar el robot sin guardar historial.

Reglas detalladas: [`CLAUDE.md`](./CLAUDE.md) §4 y
[`../docs/Arquitectura_Tecnica.md`](../docs/Arquitectura_Tecnica.md) §6 y §7.

---

## Estado actual

Esqueleto. Sin lógica todavía. Cada módulo en `src/` tiene un docstring que
describe su responsabilidad y los archivos están vacíos.

## Licencia

Por definir.
