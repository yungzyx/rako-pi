# Rako — Cerebro (rako-pi)

> Brief permanente para Claude Code. Léelo al empezar cada sesión.
> **Fuente de verdad técnica:** `../docs/Arquitectura_Tecnica.md`. Si algo aquí
> contradice ese documento, gana el documento.

---

## 1. Resumen del proyecto

**Problema.** Estudiantes universitarios que han vivido eventos estresantes o
traumáticos desarrollan patrones de evasión: postergan tareas, faltan a clases,
se aíslan. Las apps de productividad asumen voluntad disponible. La terapia es
cara, distante, lenta. Falta un acompañamiento físico, presente, sin juicio.

**Usuario.** Estudiante universitario chileno con patrones post-trauma de
evasión (no en crisis activa — ese caso siempre se deriva).

**Propuesta.** Rako es un dispositivo físico con IA en forma de robot mapache
sobre Raspberry Pi 4 + app móvil complementaria (Flutter). Detecta señales de
bloqueo (voz, actividad), responde con técnicas curadas por profesionales
(RAG sobre vault de Obsidian), acompaña con presencia (LEDs, voz cálida) y
deriva cuando hace falta.

**Este repo (`rako-pi`)** es el **cerebro** sobre la Raspberry Pi 4. No es la
app móvil ni el contenido del RAG.

```
~/Desktop/Rako/
├── docs/Arquitectura_Tecnica.md     ← fuente de verdad
├── Rako-kb/                          ← vault Obsidian (alimenta el RAG)
├── rako-pi/                          ← AQUÍ (cerebro)
└── rako-app/                         ← futuro: Flutter
```

---

## 2. Stack técnico

### En la Pi
- **Hardware actual:** Raspberry Pi 4 8GB + ReSpeaker 2-Mics Pi HAT + pantalla OLED por I2C. No hay speaker fijo todavía; salida temporal por cable a parlante externo cuando esté conectado. Ver `HARDWARE.md`.
- **OS:** Raspberry Pi OS (Debian 64-bit).
- **Lenguaje:** Python 3.12+ (Pi OS Bookworm).
- **Frameworks:** FastAPI (servicios internos — mobile API + WhatsApp webhook).
- **Vector DB:** ChromaDB (local).
- **Relacional local:** SQLite + SQLCipher (cifrado en disco).
- **Embeddings RAG:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- **Hardware GPIO:** `gpiozero`, `adafruit-circuitpython-*`.

### Cloud — arquitectura real (actualizado; ver auditoría de 2026-07)
- **LLM:** OpenAI (`gpt-4o-mini`, `llm_provider=openai`) primario, Anthropic
  Claude como fallback (`llm_provider=anthropic`). Configurable por env var.
- **STT:** Google Cloud Speech por defecto (`stt_provider=google`); OpenAI
  Whisper disponible como alternativa (`stt_provider=openai_whisper`) cuando
  está configurado.
- **TTS:** ElevenLabs primario (`tts_provider=elevenlabs`), Google Cloud TTS
  como fallback.
- **SER (emoción local):** planeado (`audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim`
  vía `transformers`/`torch`), **no implementado todavía** — ver §4.2.
- **WhatsApp:** canal de producto completo (`src/channels/whatsapp/`) sobre
  WhatsApp Business Cloud API de Meta (`whatsapp_client=cloud`). Maneja
  check-ins, menús de acción, reportes de progreso, memoria editable,
  configuración y borrado de datos — con sus propias reglas de privacidad
  (ver §4.1) y su propio chequeo de crisis (comparte `safety.detector`).
- **Backend:** Firebase (Auth + Firestore + FCM) — **diseñado pero no
  conectado todavía**: `src/sync/` tiene el cliente, el sanitizer y el
  allowlist de eventos completos y testeados, pero tanto el bootstrap de dev
  como el de Pi construyen un `FakeFirebaseClient()`. Nada se envía
  realmente a Firebase hoy; es un gap de alcance conocido, no una regresión.

### Fuera de este repo
- App móvil: **Flutter 3.x** (en `../rako-app`, no acá). El servidor FastAPI
  de este repo (`src/mobile/`) expone una API local + páginas de setup/factory
  para el primer emparejamiento vía hotspot, pero no reemplaza la app.
- Contenido RAG: vault Obsidian en `../Rako-kb` (no acá).

---

## 3. Reglas de código (siempre)

### Python
- **Python 3.12+**. Type hints en toda función pública.
- **Inmutabilidad por defecto.** Crear objetos nuevos, no mutar. `@dataclass(frozen=True)` cuando aplica.
- **Archivos chicos:** ~200–400 líneas, máximo 800. Si crece, partir.
- **Funciones cortas:** <50 líneas. Anidamiento <4 niveles. Early returns.
- **Sin números mágicos.** Constantes con nombre.
- **Errores explícitos.** Nunca `except: pass`. Nunca tragar errores. Loggear contexto.
- **Validación en bordes.** Pydantic o dataclasses para entradas externas (API, archivo, voz).
- **Formato:** `ruff format` + `ruff check`. Imports ordenados.

### Tests
- **TDD.** Test primero (rojo), implementación mínima (verde), refactor.
- **Cobertura ≥ 95%** en CI.
- **Pytest.** AAA (Arrange-Act-Assert). Nombres descriptivos del comportamiento.
- **Sin tocar APIs reales en tests.** Mocks o fixtures locales.
- **Hardware:** abstraer detrás de interfaces para poder fakear en CI.

### Git
- Commits en inglés con prefijo: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `chore:`, `perf:`, `ci:`.
- PRs: resumen + plan de prueba + qué cambia en privacidad si aplica.
- Nunca `--no-verify`. Si falla un hook, arréglalo.

### Secretos
- **Cero credenciales hardcoded.** Todo por `.env` (ver `.env.example`).
- `.env`, `*.db`, `*.sqlite*`, `*.wav`, `chroma_db/`, `models/` → `.gitignore`.

---

## 4. Restricciones críticas (NO NEGOCIABLES)

### 4.1 Privacidad
1. **Datos emocionales detallados nunca salen de la Pi.** Vector emoción,
   transcripciones completas, historial → solo SQLite local cifrado.
2. **Audio nunca se persiste.** Ni en disco, ni en cloud. Excepción única:
   audio TTS generado por el robot (es output, no input del usuario).
3. **Lo que se manda a APIs cloud:**
   - LLM (OpenAI u Anthropic, ver §2): query + chunks RAG + contexto mínimo
     anonimizado (mood agregado en 3 categorías, memoria editable solo
     `sensitivity=normal`, últimos turnos de la conversación truncados a
     180 caracteres — este último es un tradeoff revisado y aceptado, no un
     gap). **NO** nombre real, audio, vector emocional crudo, contactos.
   - STT (Google u OpenAI Whisper, según configuración): solo audio para
     transcribir, sin metadata identificable.
   - TTS (ElevenLabs o Google): solo texto a sintetizar.
   - Firebase: solo eventos no sensibles + config + agregados de progreso.
     **NO** audio, transcripciones, ni estado emocional. En Firebase no debe
     poder reconstruirse el estado emocional del usuario. (Hoy no conectado
     de verdad — ver §2.)
   - **WhatsApp (Meta Cloud API):** solo memorias `sensitivity=normal` salen
     por este canal — las sensibles nunca se envían, solo se referencia su
     cantidad ("tienes N recuerdos sensibles, revísalos en la app"). El
     número entrante debe coincidir con `channels.whatsapp_number` (el
     emparejado) antes de exponer datos, memoria, configuración o ejecutar
     borrado — un mensaje de un número no emparejado solo puede disparar el
     protocolo de crisis (si aplica) o recibe una respuesta genérica sin
     datos. El webhook de Meta se valida por firma HMAC
     (`WHATSAPP_CLOUD_APP_SECRET`) antes de procesar cualquier payload.
     Payloads salientes permitidos: check-ins, menús de acción, conteos de
     progreso sin títulos de tareas. Prohibido: transcripciones completas,
     vectores de emoción crudos, memoria sensible, detalle de crisis más
     allá del protocolo curado.
4. **Modo no-grabación** (`RAKO_MODE=private`) debe funcionar siempre: el
   robot opera pero no guarda historial de interacciones. El gate vive en
   `orchestrator/turn_session.py` (`TurnSession`), el pipeline de turno
   compartido por `RunLoop` y el loop del botón físico
   (`scripts/button_conversation.py`); también evita restaurar memoria
   conversacional desde disco en modo privado.
5. **Borrado total** desde la app o WhatsApp debe propagarse a la Pi y borrar
   TODO el historial local — no solo config de producto, también tareas,
   interacciones, estados de ánimo, logros y journal de crisis. Efecto
   inmediato (`Database.purge_all_user_data()`, invocado desde
   `UserConfigService.delete_user_data()`).
6. **Encriptación:** SQLCipher en disco; HTTPS en todas las llamadas; reglas
   estrictas de Firebase.

   **Estado actual:** `db/connection.py` usa `sqlite3` stdlib en dev (los
   wheels de SQLCipher para macOS/3.12 no están disponibles). En la Pi se
   instala `pysqlcipher3` con `libsqlcipher-dev` y `db/encryption.py`
   intercepta la apertura para aplicar `PRAGMA key`. Los repositorios son
   agnósticos al backend. **Producción NO debe correr sin SQLCipher activo:**
   `rako run` (el loop de voz real) y el lifespan de la API móvil llaman
   `Database.require_encrypted()` fuera de `rako_env=dev` y abortan si la
   base no está cifrada; `security_audit.py`/`factory_acceptance.py` marcan
   la falta de `SQLITE_ENCRYPTION_KEY` como `fail` (no `warn`) fuera de dev.

### 4.2 Manejo de crisis
1. **El LLM se BYPASSEA en crisis.** Cero generación. Respuestas pre-curadas
   por profesional, cargadas estáticamente.
2. **Disparadores de crisis — activos hoy vs. diferidos:**
   - **Activos en producción:** palabras clave de ideación suicida o
     autolesión en la transcripción (voz o WhatsApp); botón pánico físico
     (Pi) o en app/WhatsApp.
   - **Diferidos (roadmap, NO viven en producción todavía):** vector
     emocional con valores extremos sostenidos — requiere el modelo SER
     local (ver §2), que no está implementado; inactividad anormalmente
     prolongada tras interacciones de alta angustia — requiere que algo
     calcule y persista `last_high_distress_at`, y hoy nada lo hace.
     La lógica de detección para ambos ya existe en `safety/detector.py`
     con tests unitarios completos, pero ningún llamador real
     (`orchestrator/run.py`) le pasa datos vivos — **tener tests no es
     estar en producción.** No asumir que estos dos triggers protegen al
     usuario del dispositivo físico hoy.
3. **Protocolo:** presencia (no soluciones) → activar contacto de confianza
   con consentimiento previo registrado → desplegar recursos (Salud Responde
   600 360 7777, Línea Libre, etc.) → registro privado del evento
   (`crisis_journal`, en cada punto de entrada: voz, botón pánico y
   WhatsApp).
4. **Lo que el sistema NO hace en crisis:** diagnosticar, prometer
   confidencialidad absoluta, reemplazar ayuda profesional, usar frases
   motivacionales. Siempre deriva.
5. **El bypass de crisis debe estar testeado siempre.** Es la única ruta que
   no puede regresionar. CI debe fallar si el detector de crisis no atrapa los
   casos del fixture — el job dedicado `safety-fixtures` corre
   `scripts/checks.py safety`, que incluye no solo los tests puros del
   detector sino también los de integración (`orchestrator`, `RunLoop`,
   canal WhatsApp) que verifican que el veto de crisis está realmente
   cableado antes de cualquier llamada al LLM, no solo testeado en
   aislamiento.
6. **Detección de palabras clave — limitaciones conocidas:** el matcher es
   determinístico por substring (sin fuzzy matching, ver detector.py) para
   mantenerlo auditable línea por línea; cubre jerga chilena común
   ("rayarme") y algunos garbles típicos de STT, pero no tolerancia a
   errores tipográficos arbitraria — eso queda diferido hasta tener datos
   reales de campo que justifiquen el tradeoff de falsos positivos.
7. **Triage no-crisis (`safety/triage.py`):** después de que el detector
   descarta crisis, un triage graduado y determinístico diferencia:
   consejo clínico (redirección "supera mi rol"), revelación personal o
   búsqueda de ayuda profesional (derivación cálida curada a la unidad de
   bienestar configurada, sin LLM), mención de estrés/ansiedad en marco
   académico puntual (LLM con nota de tono fija — la nota es instrucción,
   no lleva datos del usuario), y ánimo bajo recurrente (≥3 días distintos
   en la semana, según check-ins locales → sube cualquier mención a
   derivación). Recomendar contactar la unidad NO es escalación activa —
   no requiere `wellbeing_escalation_enabled`. Tests en el gate de CI
   (`test_safety_triage.py`). Si el LLM falla en runtime, el turno degrada
   a una respuesta curada breve (`LLM_FALLBACK`), nunca silencio.

### 4.3 Funcionamiento offline
- Sin internet, la Pi sigue operando con respuestas pre-curadas del RAG (sin
  generación), STT/TTS local de fallback (Whisper.cpp pequeño + voz
  pre-grabada), y el botón pánico opera vía SMS gateway o Bluetooth a celular.

---

## 5. Estructura del proyecto

```
rako-pi/
├── CLAUDE.md                 ← este archivo
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── src/
│   ├── voice/                STT, TTS, wake-word
│   ├── emotion/              SER local (planeado) + análisis de patrones
│   ├── orchestrator/         decisión central + prompts + RunLoop
│   ├── rag/                  ChromaDB client + indexer + embeddings
│   ├── hardware/             GPIO: LEDs, servos, sensores, botones, audio I/O
│   ├── db/                   SQLite + SQLCipher (estado del usuario)
│   ├── sync/                 cliente Firebase (diseñado, no conectado — §2)
│   ├── safety/               detector y protocolo de crisis (bypass LLM)
│   ├── channels/whatsapp/    canal WhatsApp Business Cloud API (§2, §4.1)
│   ├── mobile/               API FastAPI local + páginas setup/factory
│   ├── product/              provisioning, OTA, fleet, security audit, etc.
│   └── productivity/         foco, coaching, mindfulness, progreso
├── tests/                    pytest
└── scripts/                  reindex_rag, setup_pi, checks.py, etc.
```

Este árbol creció mucho más allá del "cerebro mínimo" original — hay una
capa completa de producto (factory rollout, fleet, WhatsApp) no prevista en
la primera versión de este documento. Mantenerlo actualizado cuando se
agreguen módulos nuevos.

**Regla de capas.** `safety/` no depende de `orchestrator/`. `orchestrator/`
puede consultar `safety/` y debe respetar su veredicto. `hardware/` no conoce
`orchestrator/` (el orquestador habla a hardware via interfaces).

---

## 6. Cómo correr y testear

### Setup local (mac/linux para desarrollo, no la Pi)
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # rellenar con credenciales reales (no commitear)
```

Para iterar en `safety/` (no necesita las deps pesadas) basta con
`pip install pytest pytest-cov` en el venv.

### Tests
```bash
python scripts/checks.py lint         # Ruff + format check
python scripts/checks.py test         # suite completa + cobertura CI
python scripts/checks.py safety       # fixtures críticos de seguridad
python scripts/checks.py all          # harness local completo
```

### Re-indexar el RAG desde Obsidian
```bash
python scripts/reindex_rag.py
```

### Hardware en la Pi
- Tests de hardware se corren con flag: `pytest -m hardware` (requiere GPIO real).
- Sin la flag, hardware se mockea.

---

## 7. Flujos a recordar

- **Voz E2E:** mic → STT cloud → orquestador (RAG + estado SQLite)
  → LLM (OpenAI/Anthropic) → TTS cloud → parlante + LEDs + SQLite. Latencia
  objetivo 3–5s. (El paso de SER local descrito originalmente aquí está
  diferido — ver §2 y §4.2; hoy no hay lectura de emoción antes del STT.)
- **Detección proactiva:** **pendiente** — no hay un monitor de patrones
  corriendo hoy (`orchestrator/proactive.py` es un stub). El equivalente
  actual son los "smart check-ins" de WhatsApp (`channels/whatsapp/scheduler.py`),
  que sí están implementados y respetan una crisis reciente (no compiten con
  el protocolo de seguridad).
- **Botón pánico:** bypass total al LLM → protocolo curado → notifica contacto
  → muestra recursos. Latencia objetivo: contacto recibe alerta < 30 s.

Detalle completo: `../docs/Arquitectura_Tecnica.md` §4.

---

## 8. Modelo de datos (resumen)

**SQLite local (Pi, cifrado):** `tasks`, `interactions`, `emotional_states`,
`achievements`, `user_config`. **Nunca sale de la Pi.**

**Firebase (cloud):** `users/{id}` (device_id, contacto emergencia, settings),
`events/{id}` (sin contenido emocional crudo), `notifications/{id}`. Agregados
y eventos no sensibles únicamente.

Detalle: `../docs/Arquitectura_Tecnica.md` §5.

---

## 9. Antes de marcar trabajo como hecho

- [ ] Tests verdes y cobertura ≥ 95%.
- [ ] Si tocaste `safety/`, los fixtures de crisis siguen disparando.
- [ ] Nada que viole las reglas de privacidad de §4.1 sale del repo.
- [ ] No hay secretos en código.
- [ ] Si el cambio modifica qué se envía a una API cloud, está documentado.
- [ ] Si tocaste hardware, hay una abstracción mockeable.

---

## 10. Referencias

- `../docs/Arquitectura_Tecnica.md` — fuente de verdad técnica.
- `../docs/RAG_PROMPT.md` — guía de curaduría del contenido del RAG.
- `../Rako-kb/` — vault Obsidian que alimenta el RAG.
- `../Rako-kb/system_prompt_rako.md` — system prompt base del LLM.
