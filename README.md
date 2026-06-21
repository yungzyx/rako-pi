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
Para preparar varias placas, usa primero `/factory/provisioning-plan` y
`rako-doctor --factory`; ambos muestran bloqueos antes de clonar o entregar una
unidad.

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
rako-doctor --factory
rako-doctor --full
rako-doctor --calibrate --full
```

`--factory` agrega el checklist de entrega de una placa configurada: perfil,
WiFi, consentimiento, WhatsApp, bienestar, credenciales, seguridad local y los
gates manuales de micrófono, parlante, OLED, botón, foco y crisis.

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
GET  /setup
GET  /factory
GET  /status
GET  /setup/flow
POST /setup/wifi       {"ssid": "Casa", "password": "...", "apply": false}
GET  /setup/hotspot/plan
GET  /factory/report
GET  /factory/provisioning-plan
GET  /update/status
GET  /update/plan
GET  /device/identity
PATCH /device/identity {"serial": "SN-001", "lot": "pilot-a", "assigned_user_label": "nico@udd"}
POST /device/heartbeat {"status": "ok", "detail": "factory bench"}
POST /device/reset-user
GET  /onboarding/status
GET  /coach/plan
GET  /tasks?pending_only=true&limit=20
GET  /progress/today
GET  /progress/week
GET  /user/profile
PATCH /user/profile     {"preferred_name": "Nico", "university": "UDD"}
GET  /user/consent
PATCH /user/consent     {"whatsapp_enabled": true}
GET  /user/channels
PATCH /user/channels    {"wifi_ssid": "Casa", "whatsapp_number": "+569..."}
GET  /user/memory
POST /user/memory       {"text": "Prefiero bloques de 25 minutos", "category": "routine"}
DELETE /user/memory/{id}
GET  /user/export
POST /user/delete-all
POST /focus/start   {"title": "cálculo", "minutes": 30}
POST /focus/cancel
POST /whatsapp/checkin   {"to": "+56912345678"}
POST /whatsapp/progress  {"to": "+56912345678", "period": "today"}
POST /whatsapp/actions   {"to": "+56912345678"}
POST /whatsapp/inbound   {"from_number": "+56912345678", "text": "estoy bien"}
GET  /whatsapp/webhook
POST /whatsapp/webhook
```

`/setup/flow` está pensado para primer encendido o app de configuración: entrega
pasos, porcentaje de avance, próximo bloqueo, notas de privacidad y qué partes
son opcionales o manuales antes de asignar una placa.
`/setup` muestra una página local autocontenida para revisar ese flujo desde el
celular o notebook del usuario. Si expones el API en la red local, usa
`RAKO_API_TOKEN` y escribe el token en la pantalla de setup.
`/setup/wifi` puede guardar el SSID del usuario y, si `apply=true`, llamar a
NetworkManager con `nmcli`; por seguridad solo aplica cambios reales cuando
`RAKO_WIFI_APPLY_ENABLED=1`. La contraseña WiFi no se guarda en SQLite.
`/setup/hotspot/plan` genera el SSID de primer encendido y los comandos seguros
para levantar un hotspot de configuración. No inicia NetworkManager por sí solo;
usa placeholders para la clave temporal y exige `RAKO_API_TOKEN` fuera de dev.

El inbound de WhatsApp también entiende memoria editable con frases como
`recuerda que prefiero bloques de 25 minutos`, `qué sabes de mí` y
`olvida bloques de 25`. En el menú de acciones, la opción `5` devuelve un plan
rápido de estudio con bloque sugerido sin exponer títulos privados por WhatsApp;
la opción `6` muestra configuración. También entiende `pausar mensajes`,
`reanudar mensajes`, `exportar mis datos` y `borrar mis datos` con confirmación.
`/user/export` y `/user/delete-all` cubren perfil, consentimiento, canales y
memoria editable; no borran tareas ni logs operacionales.
`/factory/report` resume setup, checklist de entrega y bloqueos para producción.
`/factory/provisioning-plan` junta identidad de placa, seguridad local, hotspot,
WhatsApp, OTA y checklist de aceptación para decidir si una imagen está lista
para clonar o si una unidad está lista para handoff.
`/factory` muestra un panel local para revisar una placa: entrega, setup,
bloqueos, checks manuales, identidad, último heartbeat, versión y build.
`/device/identity` permite registrar serial, lote y asignación visible de una
placa. `/device/heartbeat` registra el último pulso local. `/device/reset-user`
borra datos del alumno anterior y tareas/estado local, pero preserva identidad
de placa y heartbeat para poder reasignarla sin mezclar memorias.
`/update/status` reporta versión/canal/build. `/update/plan` evalúa un manifest
OTA local configurado con `RAKO_UPDATE_MANIFEST_PATH`, valida canal, versión y
SHA-256 del artefacto, y devuelve los pasos de instalación segura. Aplicar OTA
sigue bloqueado por defecto con `RAKO_UPDATE_APPLY_ENABLED=0` hasta completar
releases firmadas, healthcheck e instalación con rollback.

Ejemplo de manifest:

```json
{
  "version": "0.2.0",
  "channel": "stable",
  "artifact_url": "https://example.com/rako-0.2.0.tar.gz",
  "artifact_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "rollback_version": "0.1.0",
  "minimum_version": "0.1.0",
  "release_notes": "Mejoras de producto"
}
```

Por defecto escucha en `127.0.0.1:8765`. Puedes cambiarlo con
`RAKO_API_HOST` y `RAKO_API_PORT`. Si defines `RAKO_API_TOKEN`, todos los
endpoints excepto `/health` requieren `Authorization: Bearer <token>`; en
`staging`/`prod`, el token es obligatorio.
La integración WhatsApp actual es un MVP local con cliente en memoria: permite
probar check-ins, respuestas de ánimo, menú de acciones, reportes de progreso,
inicio de foco y bypass de crisis antes de conectar WhatsApp Cloud API real.
Los mensajes salientes por WhatsApp requieren opt-in local en `/user/consent`
y número configurado en `/user/channels`. El SSID WiFi se puede guardar para
diagnóstico/onboarding, pero la contraseña WiFi no se persiste en SQLite.

Para usar WhatsApp Cloud API real:

```bash
WHATSAPP_CLIENT=cloud
WHATSAPP_CLOUD_ACCESS_TOKEN=...
WHATSAPP_CLOUD_PHONE_NUMBER_ID=...
WHATSAPP_CLOUD_VERIFY_TOKEN=...
WHATSAPP_CLOUD_APP_SECRET=...
```

`GET /whatsapp/webhook` sirve para la verificación de Meta. `POST
/whatsapp/webhook` procesa mensajes de texto entrantes; en `staging`/`prod`
exige firma `X-Hub-Signature-256` cuando `WHATSAPP_CLOUD_APP_SECRET` está
configurado.

### Smart check-ins

Rako puede evaluar si corresponde enviar un check-in proactivo sin molestar al
usuario. El scheduler respeta consentimiento, horario silencioso, intervalo
mínimo y actividad reciente.

```bash
./scripts/rako.sh smart-checkin --dry-run
./scripts/rako.sh smart-checkin
```

Para habilitarlo en una placa, el usuario debe tener `whatsapp_enabled=true`,
`proactive_messages_enabled=true` y `whatsapp_number` configurado. Si además
activa `progress_reports_enabled=true`, Rako puede celebrar progreso con conteos
seguros; no envía títulos de tareas por WhatsApp.

### Provisionar placas nuevas

Después de `scripts/setup_pi.sh`, cada placa puede quedar asignada a un usuario
con configuración local reproducible:

```bash
./scripts/rako-provision \
  --name "Nico" \
  --university "UDD" \
  --program "Ingeniería" \
  --wifi-ssid "Casa" \
  --whatsapp-number "+56912345678" \
  --enable-whatsapp \
  --enable-progress \
  --memory "Prefiere bloques de foco de 25 minutos"
```

`rako-provision` escribe perfil, consentimiento, canales y memoria editable en
SQLite. No guarda contraseñas WiFi ni secretos de APIs.

Para el flujo completo de instalación y QA por placa, ver
[`PRODUCTION_PLAN.md`](./PRODUCTION_PLAN.md).

---

## Tests

```bash
python scripts/checks.py lint                 # Ruff + format check, igual que CI
python scripts/checks.py test                 # suite completa + cobertura, igual que CI
python scripts/checks.py safety               # fixtures críticos de seguridad
python scripts/checks.py all                  # todo el harness local
```

Cobertura objetivo de CI: **≥ 95%**. El detector de crisis tiene fixtures
dedicados y no puede regresionar.

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

MVP funcional en Raspberry Pi: conversación por botón, STT/TTS, OLED/LED,
SQLite local, memoria conversacional breve, tareas/foco, reportes de progreso,
API móvil local y canal WhatsApp simulado para check-ins y acciones. Crisis y
derivación usan respuestas curadas; los reportes externos evitan títulos de
tareas por defecto.

## Licencia

Por definir.
