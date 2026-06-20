# Rako Product Journey

End-to-end product flow for turning one Raspberry Pi into a useful university
study companion.

## 1. Out of Box

The user should receive:

- Rako device with ReSpeaker mic, OLED eyes, speaker output, button, power supply
- quick-start QR or URL for setup
- clear privacy explanation: what stays local, what can go to WhatsApp, what is never sent
- university wellbeing contact defaults when available

First boot should expose a setup path:

1. connect device to power
2. connect phone to setup page/app
3. configure WiFi
4. pair WhatsApp or skip it
5. enter preferred name, university, program, timezone
6. choose consent toggles independently:
   - WhatsApp messages
   - progress reports
   - proactive coaching
   - editable memory
   - wellbeing escalation
7. run factory/first-user test: mic, speaker, OLED, button, focus flow

## 2. Daily Student Flow

Rako should improve academic performance by reducing friction, not by becoming
another dashboard.

Core loop:

1. capture the student's current intention or stuck point
2. classify whether this is focus, planning, mood, progress, crisis, or general chat
3. give one concrete next action
4. start a short block when possible
5. reflect progress visibly
6. adapt future prompts using local memory and recent behavior

Good daily interactions:

- "Rako, tengo que estudiar calculo 30 minutos"
- "No se por donde empezar"
- "Estoy bajo hoy"
- "Que hice hoy?"
- "Mañana tengo prueba, ayudame a partir"

Rako should avoid:

- long motivational speeches
- repeating "no tienes tareas pendientes" in every conversation
- exposing task titles or raw moods through WhatsApp
- acting like a therapist
- pushing messages at night or right after a recent interaction

## 3. Academic Performance Logic

Useful Rako behavior should target these mechanisms:

- Activation energy: turn vague tasks into a first 10-25 minute action.
- Attention protection: use button-first voice, short responses, and visible timer.
- Progress visibility: show counts and streak-like feedback without shame.
- Emotional load reduction: low mood leads to softer goals and mindfulness breaks.
- Context memory: remember routines and preferences locally.
- Safe escalation: crisis bypasses LLM and uses curated support.

## 4. Hardware Experience

Microphone:

- ReSpeaker must be visible in ALSA before shipping.
- `rako-doctor --record` should show nonzero RMS and no clipping.
- Capture target: clear speech at normal desk distance.
- If RMS is low, improve placement/gain before tuning software.
- If peak clips, reduce gain or increase distance.

Speaker:

- Activation cue and TTS should play through the configured output.
- Voice should be audible in a normal room without harsh volume.
- Playback failure must not crash the assistant; it should degrade to logs/text.

OLED eyes:

- Eyes should communicate state without needing text:
  - idle: calm/available
  - listening: attentive
  - thinking: subtle motion
  - speaking: warm movement
  - focus: timer/progress
  - crisis: present but not alarming
- Avoid aggressive, uncanny, or overly robotic expressions.

Button:

- Button press must start listening reliably.
- The activation sound should confirm the device heard the press.
- The LED/OLED should make state changes visible if audio is muted.

## 5. Factory Acceptance

Before assigning a board to a user:

```bash
./scripts/rako-doctor --factory
./scripts/rako-doctor --full
python scripts/checks.py safety
```

Manual acceptance:

- mic captures clear speech
- speaker plays cue and TTS
- OLED eyes are visible and friendly
- button starts listening
- focus command starts timer
- WhatsApp smart-checkin dry-run behaves as expected
- crisis phrase uses curated response

## 6. Roadmap To Product

Near term:

- real WhatsApp Cloud API adapter
- setup app or local setup web page for WiFi and pairing
- systemd timer for `smart-checkin`
- better OLED focus/mindfulness animations
- audio calibration profile per board

Mid term:

- signed OTA with rollback
- admin/factory dashboard
- support bundle without private transcripts
- device identity and account binding
- university-specific wellbeing resources

Long term:

- optional mobile app for rich progress, not required for daily use
- local wake word model tuned for "Rako"
- richer academic planner: exams, syllabi, spaced repetition, calendar
- multi-language/localization support
