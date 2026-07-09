# Runbook de presentación — Rako

> Verificado en vivo en esta Pi el 2026-07-08 (noche antes de la presentación).
> Todos los comandos se corren desde `/home/yunglab/rako-pi`.

---

## 1. Antes de salir de casa (mañana temprano)

```bash
cd /home/yunglab/rako-pi

# 1. Salud de hardware completa: OLED guiña, mic graba 2s, parlante suena
./scripts/rako-doctor --full

# 2. Gate de seguridad (272 tests de crisis, ~10 s — debe decir "272 passed")
.venv/bin/python scripts/checks.py safety

# 3. RAG sano (debe imprimir: ['descomponer-tareas#0', 'foco-y-pomodoro#1', 'arranque-minimo#1'])
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python -c "from rag.chroma_retriever import ChromaRetriever; from rag.embeddings import build_embedder; r=ChromaRetriever('./chroma_db','rako_kb',build_embedder('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')); print([c.id for c in r.query('procrastinacion', top_k=3)])"

# 4. Una vuelta real end-to-end (verifica que la API key FUNCIONA, no solo que existe)
PYTHONPATH=src .venv/bin/python -m main demo-turn "hola Rako"
```

**Internet en la sala:** STT, LLM y TTS son cloud. Enciende **Compartir
Internet** en el iPhone ANTES de llegar — la Pi se conecta sola al hotspot
`Yung 17Pro` cuando no ve el WiFi de casa (servicio `wifi-failover`).
Verifica con `ping -c1 api.openai.com`.

---

## 2. Arrancar el robot (día de la demo)

```bash
cd /home/yunglab/rako-pi && ./scripts/rako-chat
```

Eso aplica el perfil de audio, corre el doctor y deja el loop del botón
escuchando en GPIO17. **Terminal con letra grande de cara al público**: imprime
`Tú: ...`, `Rako: ...` y las latencias por etapa (captura/STT/LLM/TTS).

- **Calentamiento (importante):** antes de que entre el público, presiona el
  botón una vez y di cualquier cosa. El primer turno paga la carga de
  ChromaDB + modelo de embeddings ("Inicializando Rako..."); así el primer
  turno real sale rápido.
- Interacción: **presiona el botón del ReSpeaker → espera el tono + ojos de
  escucha → habla → deja de hablar** (corta solo tras ~0.8 s de silencio).
  NO hay wake word en este loop — no digas "Hey Rako" y esperes.
- Detener: `Ctrl+C`.
- Sala ruidosa: `./scripts/rako-chat --capture-seconds 10` y sube
  `--vad-threshold` si corta antes de tiempo.

---

## 3. Guion de demo (frases verificadas en esta Pi)

### Preguntas normales (RAG + LLM) — di al micrófono:
- «Rako, ayúdame a partir con cálculo»
- «Me distraigo con el celular cada vez que trato de estudiar, ¿qué hago?»
- «Llevo toda la semana postergando un informe, ¿por dónde parto?»
- «Falté dos semanas a clases y me da vergüenza volver, ¿cómo me pongo al día?»
- «Estoy **nervioso** por la prueba de mañana, ¿me ayudas a calmarme?» («nervioso» es seguro; «ansioso» desvía al guardarraíl)

### Barra de progreso (OLED) — di al micrófono:
- «Rako, hazme un pomodoro de **dos minutos** para estudiar cálculo»
  - 2 min = 120 s sobre barra de 120 px → **crece exactamente 1 px/seg**.
  - La barra se llena (tiempo transcurrido) mientras los dígitos bajan (restante).
  - Al llegar a 00:00: voz de cierre + carita feliz 4 s. *(Bug de cierre arreglado y verificado hoy.)*
  - **Siempre con minutos explícitos** («...de dos minutos...»), si no, Rako pregunta y no parte.
  - **NO presiones el botón mientras corre la barra** (los ojos y la barra pelean por el OLED).
  - Respaldo sin voz/botón: `PYTHONPATH=src .venv/bin/python scripts/focus_countdown.py --title "estudiar cálculo" --minutes 1 --seconds 20 --no-playback`

### Derivación (casos extremos) — MEJOR por texto en un segundo terminal:
```bash
# Derivación de bienestar (curada, SIN LLM) → Bienestar UDD + CADA UDD
PYTHONPATH=src .venv/bin/python -m main demo-turn "Necesito un psicólogo"

# Crisis (BYPASS TOTAL del LLM) → respuesta curada + Bienestar UDD + SAMU 131
PYTHONPATH=src .venv/bin/python -m main demo-turn "Ya no quiero vivir"

# Botón de pánico (simulado) → protocolo completo, notify_contact=True
PYTHONPATH=src .venv/bin/python -m main demo-crisis-panic

# Fuera de alcance clínico → "supera mi rol"
PYTHONPATH=src .venv/bin/python -m main demo-turn "¿Qué pastilla me recomiendas para dormir?"
```
Muestra al público cómo `kind=` cambia: `LLM_RESPONSE` → `WELLBEING_REFERRAL`
→ `CRISIS_PROTOCOL`. Frase clave: *«En crisis el LLM se bypassea por diseño —
cero generación, respuestas curadas por profesionales, auditable línea por línea»*.

Journal privado (solo metadatos, nunca transcripciones):
```bash
PYTHONPATH=src .venv/bin/python -c "
from config import Settings; from db.database import Database
s = Settings(); db = Database.open(s.sqlite_path, key=s.sqlite_encryption_key)
[print(tuple(r)) for r in db._conn.execute('SELECT detected_at, level, reasons, contact_notified FROM crisis_events ORDER BY recorded_at DESC LIMIT 5')]
db.close()"
```

### ⚠️ Frases PROHIBIDAS durante la demo normal
El detector es por substring y prefiere falsos positivos (por diseño). Estas
frases disparan el protocolo de crisis aunque las digas casual:
**«no puedo más», «no aguanto más», «ya para qué», «sobredosis», «violación»,
«dejar de comer»**. Y «ansioso/ansiedad/terapia/psicólogo/depresión» desvían
al guardarraíl clínico. Si alguien del público lo provoca: *«preferimos
falsos positivos — en este dominio el costo de no detectar es mucho mayor»*.

---

## 4. Planes B y C

| Falla | Plan |
|---|---|
| Mic/botón/STT | `PYTHONPATH=src .venv/bin/python scripts/chat_text.py` — escribes, Rako contesta por el parlante (ya no crashea si falla el TTS). Preséntalo como «el canal de texto». |
| Todo el audio | Los `demo-turn` del guion de derivación — todo por terminal. |
| Internet | Crisis/derivación/pánico funcionan 100% offline (curadas). La voz curada también (caché pregenerado hoy en `data/tts-cache`). Solo las preguntas LLM necesitan internet. |
| Abrir con impacto | `./scripts/rako-demo` — show guiado de 30 s (ojos + tonos + una frase hablada) sin mic ni LLM. |
| Doctor bloquea por algo cosmético | `RAKO_DOCTOR=0 ./scripts/rako-chat` |
| Parlante mudo | `./scripts/setup_respeaker_audio.sh` (rako-chat lo hace solo al partir) |
| Barra fantasma en el OLED | `pkill -f focus_countdown.py` |

---

## 5. Qué NO hacer / no prometer

- **No corras** `checks.py test` ni `pytest` a secas en vivo: 33 tests fallan
  por fuga del `.env` real (token/clave pisan los mocks) — es ambiental, no un
  bug; los mismos tests pasan 66/66 en un cwd limpio. Usa `checks.py safety`.
- **No prometas** botón de pánico físico (no está cableado al loop — la demo
  es por CLI), ni alerta real de WhatsApp (en dev es logging), ni detección
  emocional por voz (SER diferido), ni crisis en inglés (patrones solo en español).
- El robot dice **Bienestar UDD + SAMU 131** en crisis; Salud Responde
  600 360 7777 va en la alerta de WhatsApp al contacto, no en la voz.
- **No instales los servicios systemd** antes de la demo (pelearían por el
  GPIO/audio con el terminal en vivo).

---

## 6. Arreglos aplicados el 2026-07-08 (sin commitear)

1. `scripts/focus_countdown.py` — crash `AttributeError: no_stream_tts` al
   llegar la barra a 100% con playback: flags faltantes agregadas. **Verificado.**
2. `src/rag/embeddings.py` — el modelo de embeddings se cacheaba en `/tmp`
   (tmpfs): un reinicio degradaba el RAG a basura silenciosa. Ahora cachea en
   `~/.cache/fastembed` (copiado ya, 241 MB). **Verificado offline.**
3. `src/bootstrap.py` — `demo-turn` no podía abrir la base cifrada (el builder
   dev no pasaba la clave). **Verificado** (44 tests relacionados pasan).
4. `scripts/chat_text.py` — el plan B moría si ElevenLabs fallaba; ahora
   imprime el texto y sigue.
5. Instalado `pytest-cov` (para que `checks.py test/all` pueda correr) y
   pregenerado el caché de voz curada (`./scripts/rako-pregen-tts`, 10 frases).
