# Uso y operación

[Volver al proyecto](../README.md) · [Índice de documentación](README.md)

Los comandos se ejecutan desde la raíz del repositorio.

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
en un USB u otro destino. Detalle y restauración: [`INSTALL.md`](../INSTALL.md) §8.

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

## Fábrica, provisioning y flota

Flujo completo de instalación y QA por placa: [`PRODUCTION_PLAN.md`](../PRODUCTION_PLAN.md).

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
