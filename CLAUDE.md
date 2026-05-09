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
- **Lenguaje:** Python 3.12 (Pi OS Bookworm). Mantener compat 3.11+.
- **Frameworks:** FastAPI (servicios internos), LangChain (orquestación RAG+LLM).
- **Vector DB:** ChromaDB (local).
- **Relacional local:** SQLite + SQLCipher (cifrado en disco).
- **STT/TTS clients:** `google-cloud-speech`, `google-cloud-texttospeech`.
- **LLM client:** `anthropic` (Claude Haiku para MVP).
- **SER (emoción local):** `transformers` + `torch` con modelo cuantizado
  (`audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim` o liviano).
- **Embeddings RAG:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- **Hardware GPIO:** `gpiozero`, `adafruit-circuitpython-*`.

### Cloud
- **LLM:** Anthropic Claude (Haiku MVP, Sonnet si requiere más calidad).
- **Voz:** Google Cloud Speech (alternativa Azure).
- **Backend:** Firebase (Auth + Firestore + FCM).

### Fuera de este repo
- App móvil: **Flutter 3.x** + Riverpod o Bloc (en `../rako-app`, no acá).
- Contenido RAG: vault Obsidian en `../Rako-kb` (no acá).

---

## 3. Reglas de código (siempre)

### Python
- **Python 3.12** (compat 3.11+). Type hints en toda función pública.
- **Inmutabilidad por defecto.** Crear objetos nuevos, no mutar. `@dataclass(frozen=True)` cuando aplica.
- **Archivos chicos:** ~200–400 líneas, máximo 800. Si crece, partir.
- **Funciones cortas:** <50 líneas. Anidamiento <4 niveles. Early returns.
- **Sin números mágicos.** Constantes con nombre.
- **Errores explícitos.** Nunca `except: pass`. Nunca tragar errores. Loggear contexto.
- **Validación en bordes.** Pydantic o dataclasses para entradas externas (API, archivo, voz).
- **Formato:** `ruff format` + `ruff check`. Imports ordenados.

### Tests
- **TDD.** Test primero (rojo), implementación mínima (verde), refactor.
- **Cobertura ≥ 80%** en módulos no-hardware.
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
   - Claude: query + chunks RAG + contexto mínimo anonimizado. **NO** nombre
     real, audio, vector emocional crudo, contactos.
   - Google STT: solo audio para transcribir, sin metadata identificable.
   - Google TTS: solo texto a sintetizar.
   - Firebase: solo eventos no sensibles + config + agregados de progreso.
     **NO** audio, transcripciones, ni estado emocional. En Firebase no debe
     poder reconstruirse el estado emocional del usuario.
4. **Modo no-grabación** debe funcionar siempre: el robot opera pero no guarda
   historial.
5. **Borrado total** desde la app debe propagarse a la Pi y borrar SQLite
   local. Efecto inmediato.
6. **Encriptación:** SQLCipher en disco; HTTPS en todas las llamadas; reglas
   estrictas de Firebase.

   **Estado actual:** `db/connection.py` usa `sqlite3` stdlib en dev (los
   wheels de SQLCipher para macOS/3.12 no están disponibles). En la Pi se
   instala `pysqlcipher3` con `libsqlcipher-dev` y `db/encryption.py`
   intercepta la apertura para aplicar `PRAGMA key`. Los repositorios son
   agnósticos al backend. **Producción NO debe correr sin SQLCipher activo;
   el arranque hace self-test y aborta si no está cifrado.**

### 4.2 Manejo de crisis
1. **El LLM se BYPASSEA en crisis.** Cero generación. Respuestas pre-curadas
   por profesional, cargadas estáticamente.
2. **Disparadores de crisis:**
   - Palabras clave de ideación suicida o autolesión en transcripción.
   - Vector emocional con valores extremos sostenidos.
   - Botón pánico físico (Pi) o en app.
   - Inactividad anormalmente prolongada tras interacciones de alta angustia.
3. **Protocolo:** presencia (no soluciones) → activar contacto de confianza
   con consentimiento previo registrado → desplegar recursos (Salud Responde
   600 360 7777, Línea Libre, etc.) → registro privado del evento.
4. **Lo que el sistema NO hace en crisis:** diagnosticar, prometer
   confidencialidad absoluta, reemplazar ayuda profesional, usar frases
   motivacionales. Siempre deriva.
5. **El bypass de crisis debe estar testeado siempre.** Es la única ruta que
   no puede regresionar. CI debe fallar si el detector de crisis no atrapa los
   casos del fixture.

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
│   ├── emotion/              SER local + análisis de patrones
│   ├── orchestrator/         decisión central + prompts
│   ├── rag/                  ChromaDB client + indexer + embeddings
│   ├── hardware/             GPIO: LEDs, servos, sensores, botones, audio I/O
│   ├── db/                   SQLite + SQLCipher (estado del usuario)
│   ├── sync/                 cliente Firebase (solo metadatos)
│   └── safety/               detector y protocolo de crisis (bypass LLM)
├── tests/                    pytest
└── scripts/                  reindex_rag, setup_pi, etc.
```

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
pytest                                # toda la suite
pytest tests/test_safety.py -v        # solo crisis (debe pasar siempre)
pytest --cov=src --cov-report=term-missing
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

- **Voz E2E:** mic → SER local → STT cloud → orquestador (RAG + estado SQLite)
  → Claude API → TTS cloud → parlante + LEDs + SQLite. Latencia objetivo 3–5s.
- **Detección proactiva:** monitor de patrones cruza umbral → consulta RAG →
  respuesta breve (con o sin LLM según umbral) → activa robot suavemente. Si
  no responde, desescala.
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

- [ ] Tests verdes y cobertura ≥ 80% en módulos no-hardware.
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
