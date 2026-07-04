# rako-pi

[![CI](https://github.com/yungzyx/rako-pi/actions/workflows/ci.yml/badge.svg)](https://github.com/yungzyx/rako-pi/actions/workflows/ci.yml)

Cerebro de **Rako** sobre Raspberry Pi 4: un robot mapache de acompañamiento
emocional para estudiantes universitarios con patrones de evasión
post-trauma. Detecta señales de bloqueo, responde con técnicas curadas por
profesionales (RAG), acompaña con presencia física (ojos OLED, voz cálida) y
deriva a ayuda profesional cuando corresponde.

> Fuente de verdad técnica: [`../docs/Arquitectura_Tecnica.md`](../docs/Arquitectura_Tecnica.md).
> Brief para agentes de código: [`CLAUDE.md`](./CLAUDE.md).
> Instalación en una Pi nueva: [`INSTALL.md`](./INSTALL.md).

Este repo es **solo el cerebro** que corre en la Pi. La app móvil vive en
`../rako-app` (Flutter) y el contenido del RAG en `../Rako-kb` (vault de
Obsidian).

---

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
por profesionales, recursos de ayuda (Salud Responde 600 360 7777, Línea
Libre) y registro privado local. El análisis de emoción local (SER) está
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

---

## Setup

### Desarrollo local (mac / linux, sin Pi)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt   # stack liviano: tests + lint + API

cp .env.example .env
# rellenar credenciales; generar clave de cifrado con: openssl rand -hex 32
```

`requirements-dev.txt` es el mismo set que usa CI (sin torch ni SDKs de
audio). Para el runtime completo de la Pi está `requirements-pi-lite.txt`;
`requirements.txt` conserva el stack pesado experimental (SER local).
Hardware y APIs cloud se mockean en tests — la suite corre sin credenciales.

### Raspberry Pi (dispositivo real)

Guía completa paso a paso en [`INSTALL.md`](./INSTALL.md). Versión corta:

```bash
git clone https://github.com/yungzyx/rako-pi.git ~/rako-pi
cd ~/rako-pi
./scripts/setup_pi.sh      # apt + venv + deps + .env + clave SQLCipher + RAG
./scripts/rako-doctor      # salud: audio, I2C/OLED, credenciales, BD
.venv/bin/python scripts/checks.py safety   # bypass de crisis — no negociable
```

---

## Uso en el dispositivo

### Conversación por botón (flujo principal)

```bash
./scripts/rako-chat
```

Aplica el perfil de audio del ReSpeaker, corre `rako-doctor`, enciende los
ojos OLED y queda escuchando el botón. Argumentos útiles:

```bash
./scripts/rako-chat --no-playback
./scripts/rako-chat --capture-seconds 7 --audio-device plughw:seeed2micvoicec,0
RAKO_OLED=0 ./scripts/rako-chat --no-playback   # sin OLED, para depurar
```

### Diagnóstico

```bash
./scripts/rako-doctor              # chequeo estándar
./scripts/rako-doctor --full       # incluye pruebas físicas opcionales
./scripts/rako-doctor --factory    # checklist de entrega de una placa
```

Si falta el overlay del ReSpeaker (`seeed2micvoicec` no aparece en ALSA):

```bash
sudo ./scripts/rako-fix-audio-boot && sudo reboot
```

### Foco con countdown en OLED

Desde `rako-chat`, frases como estas crean un bloque de foco con countdown
visual:

```text
Rako, voy a estudiar cálculo 30 minutos
Rako, hazme un pomodoro de 10 minutos para leer papers
```

Prueba rápida sin esperar minutos reales:

```bash
PYTHONPATH=src python scripts/focus_countdown.py --title "estudiar cálculo" \
  --minutes 1 --seconds 5 --no-oled --no-playback
```

### Música ambiente y demo

```text
Rako, pon música chill      # ambiente local generado, sin Spotify/YouTube
Rako, para la música
```

```bash
./scripts/rako.sh proactive-check --dry-run   # ¿corresponde un nudge proactivo?
./scripts/rako-demo         # sesión guiada: ojos + sonido + voz, sin botón
./scripts/rako-demo-mode    # guion y comandos para demos sin datos reales
./scripts/rako.sh demo-crisis-panic   # protocolo de pánico curado (sin LLM)
```

### Respaldo local

```bash
./scripts/rako-backup       # snapshot cifrado de la BD en ./backups (rota 7)
./scripts/rako-restore      # restaura el más reciente (aparta la base actual)
```

Los datos del usuario nunca salen de la Pi, así que una SD muerta los
perdería: `rako-backup` crea snapshots consistentes (misma clave SQLCipher)
en un USB u otro destino. Detalle y restauración: [`INSTALL.md`](./INSTALL.md) §8.

### Arranque automático (systemd)

Las unidades en `systemd/` son plantillas (`__RAKO_USER__`/`__RAKO_DIR__`);
no se copian a mano. El instalador las renderiza para este usuario y ruta:

```bash
./scripts/install_systemd.sh              # rako-chat (botón+OLED) + rako-api
./scripts/install_systemd.sh --no-enable rako-api   # instalar sin arrancar
journalctl -u rako-chat -f
```

`rako.service` (loop `main run`) y `rako-chat.service` declaran `Conflicts=`
entre sí: compiten por el botón GPIO y el audio, systemd solo permite uno.

---

## API local para la app móvil

```bash
./scripts/rako-api          # uvicorn en 127.0.0.1:8765
```

La documentación interactiva vive en `http://127.0.0.1:8765/docs` (OpenAPI).
Para exportar el contrato completo (por ejemplo, para generar el cliente
Flutter):

```bash
.venv/bin/python scripts/export_openapi.py
```

Grupos de endpoints (≈50 rutas, detalle en `/docs`):

| Grupo | Qué cubre |
| --- | --- |
| `core` | `/health`, `/status`, `/pairing/info` (datos públicos de emparejamiento) |
| `setup` | primer encendido: `/setup`, `/setup/flow`, `/setup/first-run`, WiFi, hotspot, QR |
| `user` | perfil, consentimiento, canales, memoria editable, export, borrado total |
| `productividad` | tareas, `/focus/start`, progreso diario/semanal, `/coach/plan` |
| `factory` | reporte, provisioning-plan, install-plan (dry-run por defecto), checks de hardware |
| `device` | identidad de placa, heartbeat, reset de usuario, OTA (`/update/*`) |
| `whatsapp` | envíos internos, plantillas, webhook de Meta (verificación + firma) |
| `observabilidad` | `/observability`, `/security/audit`, `/support/bundle`, `/fleet/snapshot` |

Seguridad de la API:

- Escucha solo en `127.0.0.1:8765` por defecto (`RAKO_API_HOST`/`RAKO_API_PORT`).
- Con `RAKO_API_TOKEN` definido, todo excepto `/health` y `/pairing/info`
  exige `Authorization: Bearer <token>`; fuera de `dev` el token es
  **obligatorio**.
- Fuera de `dev`, el arranque aborta si la base SQLite no está cifrada
  (gate de SQLCipher en el lifespan).
- `POST /user/delete-all` ejecuta **borrado total real**: config de
  producto, tareas, interacciones, estados de ánimo, logros y journal de
  crisis (`Database.purge_all_user_data()`), con efecto inmediato.
- La contraseña WiFi nunca se persiste; `nmcli` solo se ejecuta con
  `apply=true` + `RAKO_WIFI_APPLY_ENABLED=1` (ídem hotspot con
  `RAKO_SETUP_HOTSPOT_ENABLED=1`).

---

## Canal WhatsApp

Canal de producto completo sobre WhatsApp Business Cloud API
(`src/channels/whatsapp/`): check-ins, menú de acciones, reportes de
progreso con conteos (nunca títulos de tareas), memoria editable
(`recuerda que…`, `qué sabes de mí`, `olvida…`), configuración, pausa de
mensajes, export y borrado con confirmación.

Reglas de privacidad del canal (detalle en [`CLAUDE.md`](./CLAUDE.md) §4.1):

- Solo memorias `sensitivity=normal` salen por WhatsApp; de las sensibles
  solo se informa la cantidad.
- El remitente debe coincidir con el número emparejado antes de exponer
  datos o ejecutar borrado. Un número no emparejado solo puede recibir el
  protocolo de crisis o una respuesta genérica.
- El webhook de Meta se valida por firma HMAC (`X-Hub-Signature-256`)
  antes de procesar cualquier payload; fuera de `dev`,
  `WHATSAPP_CLOUD_APP_SECRET` es obligatorio.
- La detección de crisis corre **antes** que cualquier otra rama y usa el
  mismo detector curado que la voz.

Configuración (sin credenciales usa un cliente en memoria para desarrollo):

```bash
WHATSAPP_CLIENT=cloud
WHATSAPP_CLOUD_ACCESS_TOKEN=...
WHATSAPP_CLOUD_PHONE_NUMBER_ID=...
WHATSAPP_CLOUD_VERIFY_TOKEN=...
WHATSAPP_CLOUD_APP_SECRET=...
```

### Smart check-ins

El scheduler decide si corresponde un check-in proactivo respetando
consentimiento, horario silencioso, intervalo mínimo, actividad reciente y
**crisis recientes** (no compite con el protocolo de seguridad):

```bash
./scripts/rako.sh smart-checkin --dry-run
./scripts/rako.sh smart-checkin
```

Requiere `whatsapp_enabled=true`, `proactive_messages_enabled=true` y
`whatsapp_number` configurado.

---

## Fábrica, provisioning y flota

Flujo completo de instalación y QA por placa: [`PRODUCTION_PLAN.md`](./PRODUCTION_PLAN.md).

```bash
# Valores por placa + QR/tarjeta de setup (no toca .env sin --write-env)
./scripts/rako-factory-image --serial "SN-001" --lot "pilot-a" \
  --write-env /tmp/rako-unit.env --write-card-svg /tmp/rako-setup-card.svg

# Entrega recomendada: perfil + consentimiento + canales + identidad en una operación
./scripts/rako-first-run --name "Nico" --university "UDD" \
  --wifi-ssid "Casa" --whatsapp-number "+56912345678" \
  --enable-whatsapp --enable-progress --serial "SN-001" --lot "pilot-a"

# Solo datos de usuario, sin tocar identidad de placa
./scripts/rako-provision --name "Nico" --wifi-ssid "Casa" \
  --whatsapp-number "+56912345678" --enable-whatsapp --enable-progress

# Pasos de instalación: dry-run por defecto, --apply solo ejecuta pasos "ready"
./scripts/rako-install
./scripts/rako-install --apply --step "systemd api"
```

- `/factory/provisioning-plan` y `rako-doctor --factory` muestran bloqueos
  antes de clonar una imagen o entregar una unidad.
- `/device/reset-user` borra los datos del alumno anterior preservando
  identidad de placa y heartbeat, para reasignar sin mezclar memorias.
- OTA: `/update/plan` valida canal, versión y SHA-256 contra un manifest
  local (`RAKO_UPDATE_MANIFEST_PATH`); `/update/apply` solo verifica
  artefactos cuando `RAKO_UPDATE_APPLY_ENABLED=1` y `apply=true`. El
  cambio atómico de release sigue siendo manual hasta tener releases
  firmadas end-to-end.
- `/support/bundle` (o `./scripts/rako-support-bundle`) genera un JSON
  sanitizado para soporte remoto: sin API keys, contraseñas,
  transcripciones ni memoria editable.

---

## Tests y calidad

```bash
python scripts/checks.py lint      # Ruff + format check, igual que CI
python scripts/checks.py test      # suite completa + cobertura ≥95%, igual que CI
python scripts/checks.py safety    # fixtures críticos de crisis + wiring real
python scripts/checks.py hygiene   # marcadores obsoletos, .gitignore, tamaños de archivo/función
python scripts/checks.py stress    # repite suites críticas para detectar flakiness
python scripts/checks.py all       # harness local completo
```

- Cobertura de CI: **≥ 95%** (hoy ~96%).
- El job dedicado `safety-fixtures` corre `checks.py safety`: no solo el
  detector puro, también los tests de integración que verifican que el
  veto de crisis está cableado antes del LLM en cada punto de entrada
  (orquestador, loop de voz, WhatsApp). **Esta ruta no puede regresionar.**
- `hygiene` enforza además los límites de CLAUDE.md: ≤800 líneas por
  archivo y <50 por función (con lista cerrada de casos preexistentes).

---

## RAG

```bash
python scripts/reindex_rag.py
```

Lee la vault de Obsidian (`OBSIDIAN_VAULT_PATH`, default `../Rako-kb`) y
reescribe la colección de ChromaDB en `CHROMA_DB_PATH`. Curaduría del
contenido: `../docs/RAG_PROMPT.md`.

---

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
[`CLAUDE.md`](./CLAUDE.md) §4.

---

## Estado actual

MVP funcional en Raspberry Pi: conversación por botón con memoria
conversacional breve, triage graduado de bienestar (derivación curada sin
LLM cuando corresponde), ojos OLED expresivos, tareas/foco con countdown,
API móvil local lista para Flutter (OpenAPI exportable) y canal WhatsApp
con reglas de privacidad propias. Crisis y derivación usan exclusivamente
respuestas curadas.

Diferido de forma explícita (ver [`CLAUDE.md`](./CLAUDE.md) §2 y §4.2):
SER local (emoción en audio), triggers de crisis dependientes de ese
modelo, monitor proactivo en la Pi y conexión real a Firebase.

Roadmap de producto: [`PRODUCT_ROADMAP.md`](./PRODUCT_ROADMAP.md) ·
Historia del producto: [`PRODUCT_JOURNEY.md`](./PRODUCT_JOURNEY.md) ·
Hardware: [`HARDWARE.md`](./HARDWARE.md)

## Licencia

Por definir.
