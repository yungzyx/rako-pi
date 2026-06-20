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

## Next production milestones

1. WhatsApp Cloud API adapter with template support.
2. Mobile setup app for WiFi provisioning and QR pairing.
3. Signed OTA update + rollback.
4. Device identity and cloud account binding.
5. Sanitized support bundle for debugging deployed devices.
6. Systemd units checked into repo and installed by `setup_pi.sh`.
7. Hardware fixture checklist for speaker/mic/OLED/button before shipping.
