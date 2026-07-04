# Instalación en una Raspberry Pi nueva

Guía de cero a Rako funcionando: flashear la SD, clonar el repo, instalar,
configurar credenciales y dejar los servicios corriendo en boot. Pensada
para reconstruir el dispositivo desde `main` sin depender de nada que
viviera solo en la SD anterior.

Hardware esperado: Raspberry Pi 4 (8 GB), ReSpeaker 2-Mics Pi HAT, pantalla
OLED SSD1306 por I2C. Detalle en `HARDWARE.md`.

---

## 1. Flashear la SD

1. Raspberry Pi Imager → **Raspberry Pi OS (64-bit)** reciente. Se requiere
   Python 3.12+ (`setup_pi.sh` lo verifica y aborta si no); Bookworm trae
   3.11, así que usar Trixie o superior — o instalar 3.12+ aparte y correr
   el setup con `PYTHON_BIN=python3.12`.
2. En las opciones del Imager configurar: hostname, usuario (cualquier
   nombre — nada en este repo depende del username), Wi-Fi y SSH.
3. Bootear la Pi y entrar por SSH.

## 2. Habilitar interfaces de hardware

```bash
sudo raspi-config
# Interface Options → I2C → Enable      (OLED)
# Interface Options → SPI → Enable      (opcional, NeoPixel por SPI)
sudo reboot
```

El ReSpeaker 2-Mics necesita su overlay de audio; si el micrófono no
aparece tras el primer boot, ver la sección de audio de `HARDWARE.md` y
`scripts/setup_respeaker_audio.sh` (el servicio `rako-chat` lo corre
automáticamente en cada arranque).

## 3. Clonar e instalar

```bash
git clone https://github.com/yungzyx/rako-pi.git ~/rako-pi
cd ~/rako-pi
./scripts/setup_pi.sh
```

El script es idempotente (se puede re-correr). Hace:

- `apt install` de dependencias del sistema (SQLCipher, PortAudio, ffmpeg,
  i2c-tools…).
- Agrega el usuario a los grupos `gpio,i2c,spi,audio` (requiere re-login
  para tomar efecto).
- Crea `.venv` (exige Python 3.12/3.13) e instala
  `requirements-pi-lite.txt` — el stack liviano de runtime, sin
  torch/transformers (el SER local está diferido; ver `CLAUDE.md` §2).
- Copia `.env.example` → `.env` y genera `SQLITE_ENCRYPTION_KEY`
  automáticamente si está vacía.
- Indexa el RAG si encuentra la vault de Obsidian (`OBSIDIAN_VAULT_PATH`,
  por defecto `../Rako-kb`).

## 4. Credenciales en `.env`

Editar `~/rako-pi/.env` y completar como mínimo:

| Variable | Para qué | Dónde se obtiene |
| --- | --- | --- |
| `OPENAI_API_KEY` | LLM principal (`gpt-4o-mini`) y STT Whisper opcional | platform.openai.com |
| `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` | TTS principal (voz cálida) | elevenlabs.io |
| `GOOGLE_APPLICATION_CREDENTIALS` | STT por defecto + TTS fallback | JSON de service account de Google Cloud (copiarlo a la Pi, p. ej. `~/rako-pi/google-credentials.json`) |
| `ANTHROPIC_API_KEY` | LLM fallback (opcional pero recomendado) | console.anthropic.com |

Para producción real (uso con una persona, no pruebas):

- `RAKO_ENV=prod` — activa el gate de cifrado: `rako run` y la API móvil
  **abortan** si la base no está cifrada con SQLCipher.
- `RAKO_API_TOKEN` — obligatorio fuera de dev para la API móvil.
- `WHATSAPP_CLOUD_APP_SECRET` — obligatorio fuera de dev si se usa el
  webhook de WhatsApp.

`SQLITE_ENCRYPTION_KEY` ya quedó generada por el setup. **Respaldarla**
(gestor de contraseñas): sin ella, los datos locales cifrados son
irrecuperables.

## 5. Verificar antes de usar

```bash
cd ~/rako-pi

# 1. Salud del dispositivo: audio, I2C/OLED, credenciales, BD, RAG.
./scripts/rako-doctor

# 2. Bypass de crisis — no negociable antes de usar con una persona.
.venv/bin/python scripts/checks.py safety

# 3. Turno de prueba end-to-end (texto, sin hardware).
./scripts/rako.sh demo-turn "hola Rako"

# 4. Protocolo de pánico curado (sin LLM).
./scripts/rako.sh demo-crisis-panic
```

Si `rako-doctor` reporta bloqueadores, arreglarlos antes de seguir — el
servicio `rako-chat` corre el mismo chequeo en cada arranque y no inicia
si falla (bypass explícito: `RAKO_DOCTOR=0`).

## 6. Provisionar para un usuario

```bash
./scripts/rako-provision --name "Nico" --wifi-ssid "Casa" \
  --whatsapp-number "+569..." --enable-whatsapp --enable-progress
```

El número de WhatsApp que se registra acá es el **único** autorizado a
leer datos/memoria/configuración por ese canal (ver `CLAUDE.md` §4.1).

## 7. Autostart con systemd

Las unidades en `systemd/` son plantillas (tokens `__RAKO_USER__` /
`__RAKO_DIR__`); el instalador las renderiza para el usuario y la ruta
reales de esta instalación:

```bash
./scripts/install_systemd.sh
```

Sin argumentos instala y arranca el stack por defecto:

- **`rako-chat`** — loop físico: botón del ReSpeaker + ojos OLED
  (`scripts/rako-chat`, que además configura el audio y corre
  `rako-doctor` en cada boot).
- **`rako-api`** — API móvil local en `127.0.0.1:8765` (emparejamiento y
  app Flutter).
- **`rako-backup.timer`** — snapshot cifrado diario de la base a las
  04:00 (destino por defecto `./backups`; ver §8 para apuntarlo a USB).

Alternativa: `./scripts/install_systemd.sh rako` instala el loop
`python -m main run` (bus de eventos de hardware). `rako` y `rako-chat`
declaran `Conflicts=` entre sí porque compiten por el botón GPIO y el
audio — systemd no deja correr ambos.

Opt-in adicional: `./scripts/install_systemd.sh rako-proactive` agenda el
chequeo proactivo cada 30 minutos (nudge suave por voz si hay tareas
pendientes + inactividad larga; respeta modo privado, crisis reciente,
horario silencioso y rate limit). Probar antes con
`./scripts/rako.sh proactive-check --dry-run`.

```bash
# Logs en vivo
journalctl -u rako-chat -f
journalctl -u rako-api -f

# Estado
systemctl status rako-chat rako-api
```

## 8. Respaldos locales (recomendado)

Una microSD muerta no debe borrar la historia del usuario (los datos, por
diseño, nunca salen de la Pi). `rako-backup` crea un snapshot consistente
de la base SQLite — cifrado con la misma `SQLITE_ENCRYPTION_KEY` — y rota
los antiguos:

```bash
./scripts/rako-backup                                # ./backups, conserva 7
./scripts/rako-backup --output-dir /media/usb/rako --keep 14
./scripts/rako-backup --list
```

El instalador de systemd ya agenda un backup diario a las 04:00
(`rako-backup.timer`, destino `./backups`). Para protección real contra
muerte de la microSD, apuntarlo a un USB montado: editar `ExecStart` en
`/etc/systemd/system/rako-backup.service` (`--output-dir /media/usb/rako`)
y `sudo systemctl daemon-reload`.

Restaurar un snapshot (valida la clave, aparta la base actual como copia
`pre-restore` y deja el snapshot en su lugar):

```bash
sudo systemctl stop rako-chat rako-api
./scripts/rako-restore                 # usa el snapshot más reciente
./scripts/rako-restore backups/rako-db-20260704-040000.db
sudo systemctl start rako-chat rako-api
```
Para restaurar: detener los servicios (`sudo systemctl stop rako-chat rako-api`),
copiar el snapshot sobre la ruta de `SQLITE_PATH` (borrando `*-wal`/`*-shm`
si existen) y volver a arrancar. **Respaldar también la clave**: sin
`SQLITE_ENCRYPTION_KEY` el snapshot es irrecuperable.

## 9. Emparejar la app móvil

Con `rako-api` corriendo, la Pi expone la API local documentada en
`/docs` (OpenAPI). El flujo de primer emparejamiento vía hotspot está en
`src/mobile/` (páginas de setup/factory); `GET /pairing/info` entrega los
datos públicos de emparejamiento. El detalle del contrato para Flutter se
puede exportar con:

```bash
.venv/bin/python scripts/export_openapi.py
```

---

## Problemas comunes

| Síntoma | Causa probable | Fix |
| --- | --- | --- |
| `rako-doctor` no ve el micrófono | Overlay del ReSpeaker no cargado | `scripts/setup_respeaker_audio.sh` y revisar `HARDWARE.md` |
| OLED en negro | I2C deshabilitado o cableado | `sudo raspi-config` → I2C; `i2cdetect -y 1` debe mostrar `3c` |
| `rako run` aborta con error de cifrado | `RAKO_ENV != dev` sin SQLCipher/clave | Instalar `sqlcipher3` (lo hace `setup_pi.sh`) y verificar `SQLITE_ENCRYPTION_KEY` en `.env` |
| Sin voz de salida | No hay parlante conectado (no hay speaker fijo aún) | Conectar parlante por jack; ver `HARDWARE.md` |
| Grupos gpio/i2c sin efecto | La sesión SSH es anterior al `usermod` | Salir y volver a entrar (o rebootear) |
| Wake word no disponible | `pvporcupine` no se instala por defecto | Descomentar en `requirements-pi-lite.txt` + `PICOVOICE_ACCESS_KEY`; el loop por botón no lo necesita |
