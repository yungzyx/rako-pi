# Rako — Product Roadmap

Last updated: 2026-06-11

## Product north star

Rako is a physical personal/emotional companion for students with avoidance patterns. It should not be a passive chatbot. It should notice context, suggest the next small action, support task initiation, and provide gentle accountability without shame.

## Core loops

### 1. Start a task / focus loop

Trigger examples:

- “Voy a empezar a estudiar.”
- “Rako, acompáñame con esta tarea.”
- “Hazme un pomodoro de 25 minutos.”
- Physical button → user says task.

Expected behavior:

1. Extract or ask for a short task title.
2. Create local task as `IN_PROGRESS`.
3. Start a focus countdown, default 25 minutes unless user says a duration.
4. OLED expression: `listening` → `thinking` → `focus`/`neutral`.
5. Rako says one concrete starting step, not a long plan.
6. Optional opt-in external alert: “Rako empezó una sesión de foco.” No transcript or emotional data.

### 2. During focus

- OLED can blink slowly / calm neutral.
- If user checks in: give progress encouragement.
- If timer ends: ask if they want break, continue, or mark done.
- Avoid guilt language.

### 3. Inactivity / avoidance

Signals:

- No interaction for long time after a task was started.
- Many pending tasks and no recent completions.
- User language suggests overwhelm.

Expected behavior:

- Soft proactive prompt: “¿Hacemos solo 5 minutos?”
- OLED expression: `bored` or `sleepy` for idle; `thinking` for proactive.
- Do not spam; rate-limit nudges.

### 4. Emotional support

Rako should be more directive than a generic assistant, while staying safe:

- Reflect briefly.
- Suggest one concrete next action.
- Offer to start a timer or break task down.
- In crisis, bypass LLM and use safety protocol.

### 5. External notifications / WhatsApp

Default: external notifications are opt-in and privacy-preserving.

Allowed safe payloads:

- task started/completed metadata
- focus session started/ended
- non-sensitive device heartbeat

Not allowed:

- full transcript
- emotional vector
- crisis details beyond existing panic protocol
- private task descriptions unless user explicitly opts in

### 6. Product onboarding / multi-user loop

Each physical Rako must be assigned to one user before it behaves like a
product. The app or setup flow should collect:

- preferred name, university/program, locale, timezone
- WiFi SSID/status without persisting the WiFi password
- WhatsApp number and explicit channel opt-in
- proactive-message and progress-report consent
- trusted contact and wellbeing unit information
- editable memory such as study preferences, routines, motivation style, and
  boundaries

Readiness is explicit: `/onboarding/status` reports missing setup fields so the
app can guide the user without guessing.

## Implementation phases

### Phase A — Foundation

- Pure Python focus-session model.
- Voice intent parser for task/focus commands.
- OLED state mapper.
- Notification event policy for WhatsApp/Firebase hooks.

### Phase B — Runtime integration

- Button conversation can detect task/focus intent.
- Start timer in process and show OLED state.
- Store task in SQLite.
- Queue safe sync event.

### Phase C — Product polish

- Proactive inactivity monitor.
- Break suggestions.
- Task completion / achievement loop.
- User preference config: default focus minutes, WhatsApp opt-in, quiet hours.

### Phase D — Robust wake/productization

- Porcupine custom wake word.
- Systemd services for Rako loop + OLED status.
- Hardware-safe LED plan not using GPIO18.

### Phase E — Multi-user product foundation

- Local product profile over `user_config`.
- Editable memory controlled by the user.
- Channel consent gates for WhatsApp outbound messages.
- Mobile API endpoints for profile, consent, channels, memory, and onboarding
  status.
- Next: pair device to cloud account, signed OTA updates, WhatsApp Cloud API
  adapter, and app-side WiFi provisioning.
