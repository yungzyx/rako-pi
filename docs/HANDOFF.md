# Handoff — estado del proyecto tras la sesión de reconstrucción (2026-07)

> **Para el próximo agente / la próxima sesión (incluido el Claude Code de
> la Pi):** léeme primero, junto con `CLAUDE.md` (brief permanente) y
> `git log --oneline -20`. Este archivo resume la sesión larga en que se
> reconstruyó y endureció el proyecto tras perder la SD; los detalles
> técnicos viven en `CLAUDE.md`, `INSTALL.md` y los mensajes de commit.

## Contexto

La microSD de la Raspberry Pi 4 murió y se perdieron ~3 días de trabajo
local no subido. Se reconstruyó y mejoró todo desde el repo. El código
está en `main`, todo con CI verde. La Pi nueva ya tiene SD; el próximo
paso real es el **bring-up del hardware** (ver `INSTALL.md`).

## Decisión de arquitectura (no revertir sin discutir)

**"Local para lo que protege, cloud para lo que encanta."** Seguridad,
privacidad y resiliencia offline corren SIEMPRE local (detector de crisis
determinístico, SQLCipher, frases curadas pre-generadas, whisper.cpp de
fallback). Conversación y voz usan APIs cloud como primarias — la calidad
conversacional es el producto y un modelo local en Pi 4 la degradaría.
El SER local (emoción en audio) está **diferido** hasta tener datos de
campo; sus dependencias (torch/transformers) NO están en requirements.
`requirements.txt` es solo un puntero a `requirements-pi-lite.txt`.

## Qué se hizo en esta sesión (por bloques)

1. **Instalación limpia (Fase 5)** — deps faltantes en
   `requirements-pi-lite.txt` (openai, Pillow, luma.oled,
   google-cloud-texttospeech); unidades systemd convertidas en plantillas
   (`__RAKO_USER__`/`__RAKO_DIR__`) + `scripts/install_systemd.sh`;
   `INSTALL.md` de cero a funcionando.
2. **Docs profesionales** — README reescrito, HARDWARE/PRODUCTION_PLAN al día.
3. **Pipeline de voz unificado** — `orchestrator/turn_session.py`
   (`TurnSession`) es el pipeline compartido por `RunLoop` y el loop del
   botón (`scripts/button_conversation.py`): memoria, triage,
   persistencia con gate de privacidad, comando "recuerda que" con veto
   de crisis primero. `FallbackTTS` (degradación en runtime).
4. **Backups** — `rako-backup` (snapshot cifrado con rotación) +
   `rako-restore` (restauración validada) + timer diario systemd.
5. **Seguridad crítica** — alerta REAL al contacto de confianza vía
   WhatsApp con consentimiento (`channels/whatsapp/crisis_notifier.py`);
   migraciones de BD versionadas (`db/migrations.py`); voz de crisis
   offline (`rako-pregen-tts` + `voice/tts_cache.py`); trigger de
   inactividad post-angustia ahora ACTIVO (datos vivos desde
   `orchestrator/context.py`).
6. **Calidad/operación** — pisos de cobertura por archivo; 110 evals de
   conversación (`test_conversation_quality.py`); `docs/CLINICAL_REVIEW.md`;
   job de stress semanal en CI.
7. **Refactor + latencia** — `whatsapp/service.py` partido (807→343) en
   módulos por dominio; TTS por oraciones + streaming real (ElevenLabs
   `/stream` a mpg123); sinónimos de "recuerda que".
8. **Features finales** — STT offline (whisper.cpp, `voice/stt_local.py`);
   monitor proactivo (`orchestrator/proactive.py` + comando
   `proactive-check` + timer opt-in); aprendizaje de preferencias opt-in
   (`orchestrator/preferences.py` — Rako pregunta antes de guardar).
9. **Derivación a bienestar en AMBOS canales** — el triage graduado
   (`safety/triage.py`) corre por voz y por WhatsApp: derivación cálida a
   la unidad configurada o redirección clínica, solo texto curado.

Estado de tests: ~990 tests, cobertura ≥95% global + pisos por archivo,
gate de seguridad dedicado (`scripts/checks.py safety`). Todos verdes.

## Pendientes — del usuario (bloquean el piloto)

- **Revisión clínica**: `docs/CLINICAL_REVIEW.md` (14 ítems). El más
  importante antes de usar con una persona real.
- **WhatsApp Cloud producción**: aprobar plantillas con Meta + webhook público.
- **Firebase**: decidir conectar o eliminar (recomendación: eliminar
  salvo que Flutter necesite push).
- **Wake word**: cuenta Picovoice + entrenar "Oye Rako" (.ppn).

## Pendientes — que necesitan la Pi física (para el Claude de la Pi)

- **Bring-up**: `setup_pi.sh` → `rako-doctor` → `checks.py safety` →
  `rako-pregen-tts` → `rako-chat`. Ver `INSTALL.md`.
- **ReSpeaker**: overlay conocido-bueno + calibración de audio en
  `HARDWARE.md`; `rako-fix-audio-boot` si el mic no aparece.
- **STT offline (opcional)**: compilar whisper.cpp, apuntar
  `WHISPER_CPP_BIN`/`WHISPER_CPP_MODEL` en `.env`.
- **Timers opt-in**: `install_systemd.sh rako-proactive`.
- **LEDs**: bloqueados por conflicto GPIO18/I2S del ReSpeaker — elegir
  pin/controlador alternativo antes de cablear el anillo.
- **Botón de pánico físico dedicado** (el del ReSpeaker es conversación).

## Recordatorios operativos

- **Respaldar `SQLITE_ENCRYPTION_KEY`** aparte: sin ella los backups son
  irrecuperables.
- Producción (`RAKO_ENV != dev`) aborta si la base no está cifrada.
- Rako y rako-chat declaran `Conflicts=` entre sí (compiten por botón/audio).
- No editar copy de crisis/derivación sin registrar la revisión en
  `docs/CLINICAL_REVIEW.md`.

## Cómo trabajan las dos sesiones en paralelo

- **Sesión web (claude.ai/code)**: cambios sobre el repo remoto; pushea a
  `main`. La Pi hace `git pull`.
- **Claude Code en la Pi**: todo lo que toca hardware real; commitea y
  pushea sus arreglos para que la sesión web los vea.
- Se sincronizan por git.
