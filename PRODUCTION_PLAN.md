# Rako Production Plan

Operational plan for producing many Raspberry Pi based Rako devices.

## Per-board factory flow

1. Flash Raspberry Pi OS 64-bit.
2. Enable SSH/I2C/SPI/audio groups as needed.
3. Clone this repo into `~/rako-pi`.
4. Run base setup:

```bash
cd ~/rako-pi
./scripts/setup_pi.sh
```

5. Fill `.env` with production credentials:

- `OPENAI_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `RAKO_API_TOKEN`
- `SQLITE_ENCRYPTION_KEY`

6. Provision the user/device:

```bash
./scripts/rako-provision \
  --name "Nico" \
  --university "UDD" \
  --program "Ingeniería" \
  --wifi-ssid "Casa" \
  --whatsapp-number "+56912345678" \
  --trusted-contact-name "Contacto de apoyo" \
  --trusted-contact-phone "+56911111111" \
  --wellbeing-unit-name "Bienestar UDD" \
  --wellbeing-unit-phone "+56228203419" \
  --enable-whatsapp \
  --enable-progress \
  --enable-proactive \
  --enable-wellbeing \
  --memory "Prefiere bloques de foco de 25 minutos"
```

7. Run checks:

```bash
./scripts/rako-doctor --factory
./scripts/rako-doctor
./scripts/rako-doctor --full
python scripts/checks.py safety
```

8. Run a human acceptance test:

- button press starts listening
- STT captures a short phrase
- Rako answers without robotic repetition
- focus command starts a timer
- WhatsApp check-in requires consent
- WhatsApp menu `2 -> 25 -> estudiar cálculo` starts focus
- crisis phrase uses curated response
- `/onboarding/status` returns `ready: true`

## Conversation quality gates

Every release should test:

- follow-up continuity: "sigamos" should not restart the conversation
- focus intent: "conteo de 30 minutos de estudiar" should not produce broken text
- memory adaptation: normal editable memory can influence tone
- sensitive memory: never sent to LLM context
- crisis/scope: bypass LLM when crisis is detected

## Product capability plan

For a multi-user product, Rako should grow around small, consented capabilities
that work the same on every board:

- Provisioning: each device must have a local profile, device/user identity,
  WiFi setup state, WhatsApp number, trusted contact, wellbeing unit, and
  explicit consent flags.
- Memory: store editable normal memories locally; never send sensitive memory
  to external channels unless the user explicitly enables that category.
- Proactive coaching: choose the next WhatsApp touchpoint from local signals:
  recent low mood, completed work, active tasks, pending tasks, or no plan.
- Mindfulness breaks: keep a local library of short, safe exercises such as
  breath awareness, short body scan, mindful walking, and stretch/breathe.
- Progress visibility: send privacy-safe counts by default; task titles stay
  inside authenticated local/mobile views.
- Safety escalation: crisis handling must use curated text and local resources
  first, with trusted contact/wellbeing escalation only when configured and
  consented.
- Fleet readiness: installation scripts, systemd units, health checks, support
  bundles, OTA/rollback, and per-board acceptance tests must be repeatable.

## WhatsApp product gates

Outbound WhatsApp must be opt-in:

- `whatsapp_enabled=true`
- `whatsapp_number` configured
- `progress_reports_enabled=true` for progress reports

Allowed outbound payloads:

- safe check-ins
- action menus
- progress counts without private task titles

Disallowed outbound payloads:

- full transcripts
- raw emotion vectors
- sensitive memory
- crisis details beyond curated resources

Smart check-ins must also be opt-in:

- `whatsapp_enabled=true`
- `proactive_messages_enabled=true`
- Progress celebration requires `progress_reports_enabled=true`
- Messages may include counts and general next actions, never task titles
- Scheduler should avoid quiet hours, throttle repeated sends, and skip if the
  user interacted recently.

## Mindfulness content notes

The first local exercise library is based on common guidance from Mayo Clinic,
NHS/Guys and St Thomas, and APA resources:

- mindful breathing as a short stress reset
- body scan to notice body sensations and tension
- sitting meditation/awareness of breath
- mindful walking and gentle stretch/breathe as study breaks

Rako should frame these as study-support practices, not therapy. If an exercise
is painful, uncomfortable, or the user signals crisis, Rako should stop the
exercise path and use the safety protocol.

## Next production milestones

1. WhatsApp Cloud API adapter with template support.
2. Mobile setup app for WiFi provisioning and QR pairing.
3. Signed OTA update + rollback.
4. Device identity and cloud account binding.
5. Sanitized support bundle for debugging deployed devices.
6. Systemd units checked into repo and installed by `setup_pi.sh`.
7. Hardware fixture checklist for speaker/mic/OLED/button before shipping.
8. Admin/factory dashboard for assigning devices to users and checking readiness.
9. Consent review screen where users can pause WhatsApp, progress, proactive
   messages, memory, and wellbeing escalation independently.
