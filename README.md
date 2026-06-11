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
→ parlante + LEDs/OLED + SQLite + sync Firebase`. Detalle completo en el
[doc de arquitectura](../docs/Arquitectura_Tecnica.md).

Hardware actual de la Pi: Raspberry Pi 4 8GB + ReSpeaker 2-Mics Pi HAT + OLED I2C. Por ahora no hay speaker fijo; se usará salida de audio a parlante externo por cable cuando esté conectado. Ver [`HARDWARE.md`](./HARDWARE.md).

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

### Ejecutar Rako físico desde terminal

```bash
rako-chat
```

Ese comando aplica el perfil de audio del ReSpeaker, corre un diagnóstico rápido,
enciende los ojos OLED y deja escuchando el botón del ReSpeaker. Para pasar
argumentos al listener:

```bash
rako-chat --no-playback
rako-chat --capture-seconds 7 --audio-device plughw:seeed2micvoicec,0
rako-chat --cue-volume 0.14 --playback-warmup-seconds 0.15
```

Si quieres apagar OLED para depurar:

```bash
RAKO_OLED=0 rako-chat --no-playback
```

### Diagnóstico rápido de producto

```bash
rako-doctor
```

Chequea Python, `.env`, comandos de audio/GPIO, ReSpeaker, STT, TTS y ruta de
SQLite. Para pruebas físicas opcionales:

```bash
rako-doctor --full
rako-doctor --calibrate --full
```

### Foco con countdown en OLED

Desde `rako-chat`, frases como estas crean un bloque de foco y lanzan un
countdown visual en la OLED:

```text
Rako, voy a estudiar cálculo 30 minutos
Rako, hazme un pomodoro de 10 minutos para leer papers
```

Al terminar, Rako avisa por voz y sugiere una pausa breve. Para probar el timer
sin esperar minutos reales:

```bash
PYTHONPATH=src python scripts/focus_countdown.py --title "estudiar cálculo" --minutes 1 --seconds 5 --no-oled --no-playback
```

### Música chill local

```text
Rako, pon música chill
Rako, para la música
```

Por ahora es un ambiente local generado por Rako, sin Spotify/YouTube.

### Demo guiada sin botón

```bash
rako-demo
```

Muestra ojos, sonidos y una respuesta hablada simulando una sesión de foco. Útil
para verificar la experiencia completa sin depender del botón ni de una frase
perfecta.

### Arranque automático al enchufar/prender la Pi

El repo trae una unit opcional en `systemd/rako-chat.service`. No se habilita
sola: primero conviene probar audio + OLED manualmente. Para instalarla:

```bash
sudo cp systemd/rako-chat.service /etc/systemd/system/rako-chat.service
sudo systemctl daemon-reload
sudo systemctl enable --now rako-chat.service
journalctl -u rako-chat.service -f
```

Para detener/desactivar:

```bash
sudo systemctl disable --now rako-chat.service
```

### API local para app móvil

La app móvil puede hablar con la Pi por la red local. El primer contrato expone
estado y foco:

```bash
rako-api
```

Endpoints iniciales:

```text
GET  /health
GET  /status
GET  /tasks?pending_only=true&limit=20
GET  /progress/today
GET  /progress/week
POST /focus/start   {"title": "cálculo", "minutes": 30}
POST /focus/cancel
POST /whatsapp/checkin   {"to": "+56912345678"}
POST /whatsapp/progress  {"to": "+56912345678", "period": "today"}
POST /whatsapp/actions   {"to": "+56912345678"}
POST /whatsapp/inbound   {"from_number": "+56912345678", "text": "estoy bien"}
```

Por defecto escucha en `0.0.0.0:8765`. Puedes cambiarlo con
`RAKO_API_HOST` y `RAKO_API_PORT`. Si defines `RAKO_API_TOKEN`, todos los
endpoints excepto `/health` requieren `Authorization: Bearer <token>`.
La integración WhatsApp actual es un MVP local con cliente en memoria: permite
probar check-ins, respuestas de ánimo, menú de acciones, reportes de progreso,
inicio de foco y bypass de crisis antes de conectar WhatsApp Cloud API real.

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
