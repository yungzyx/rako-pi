# Rako Pi — Hardware actual

Fecha de actualización: 2026-07-04

## Raspberry

- Raspberry Pi 4
- RAM: 8 GB
- OS esperado: Raspberry Pi OS / Debian 64-bit

## Audio input

- ReSpeaker 2-Mics Pi HAT
- Uso esperado:
  - micrófono principal para wake word / captura de voz
  - entrada para STT cloud o fallback offline
- Nota: cualquier implementación de audio debe detectar dispositivos disponibles y degradar con error claro si el HAT no aparece.

## Audio output

- Actualmente no hay speaker interno/cableado permanente.
- Salida temporal esperada:
  - conectar cable de audio a un parlante externo cuando sea necesario.
- Implicación de software:
  - no asumir parlante siempre presente;
  - TTS puede generar audio, pero playback debe tolerar ausencia de dispositivo;
  - conviene tener modo texto/log para pruebas sin parlante.

## Pantalla

- OLED SSD1306 128x64 por I2C (dirección `0x3c`, verificar con
  `i2cdetect -y 1`). Renderizada con `luma.oled` + Pillow.
- Uso actual (implementado en `eyes.py` + `src/hardware/oled_runtime.py`):
  - ojos expresivos estilo anime — idle, escuchando, pensando, hablando,
    feliz, foco, error, crisis/protocolo — con parpadeo y transiciones;
  - no depender solo de LEDs/voz para feedback.

## Activadores de conversación

### Botón físico

- El botón superior del ReSpeaker 2-Mics Pi HAT se usará como activador confiable inmediato.
- Pin esperado: BCM GPIO17.
- Script de prueba:

```bash
cd ~/rako-pi
source .venv/bin/activate
PYTHONPATH=src python scripts/button_conversation.py --no-playback
```

### Wake word acústico

- No usar Google STT como activador principal: confunde “Rako” con palabras como “gato”, “flaco” o “chato”.
- Motor recomendado: Porcupine con keyword custom entrenada para “Oye Rako” / “Hola Rako”.
- Config esperada:
  - `WAKE_WORD_ENGINE=porcupine`
  - `PORCUPINE_ACCESS_KEY=...`
  - `PORCUPINE_KEYWORD_PATH=./models/oye-rako.ppn`

## ReSpeaker — instalar el overlay WM8960 (VERIFICADO en Trixie / kernel 6.18)

**En una SD/OS nuevo el `.dtbo` compilado NO viene instalado.**
`scripts/rako-fix-audio-boot` solo agrega el overlay a `config.txt` y
aborta con "Missing seeed-2mic-voicecard.dtbo overlay" si el `.dtbo` no
está en `/boot/firmware/overlays/` — no lo compila ni lo instala. Síntoma
típico: `rako-doctor` reporta "falta dtoverlay=seeed-2mic-voicecard" y
`arecord -L` no muestra `seeed2micvoicec` aunque hayas corrido el fix.

**NO hace falta el DKMS de `respeaker/seeed-voicecard`.** El instalador
clásico está roto en Bookworm/Trixie y no compila contra kernels 6.x
recientes — pero no se necesita. El overlay del repo
(`hardware/overlays/seeed-2mic-voicecard-micbias-fix.dts`) está escrito
contra drivers **mainline que ya vienen en el kernel**: el codec
`snd-soc-wm8960` (`compatible = "wlf,wm8960"`) y el machine driver
`snd-soc-simple-card` (`compatible = "simple-audio-card"`). Solo hay que
compilar ese `.dts` con `dtc` e instalar el `.dtbo`. El nombre ALSA que
declara (`simple-audio-card,name = "seeed-2mic-voicecard"`) queda, tras el
stripping de ALSA a 15 chars, como card id `seeed2micvoicec` — el mismo
que daría el DKMS y el que esperan todos los scripts de Rako
(`plughw:seeed2micvoicec,0`).

Procedimiento verificado (Pi 4, Debian 13 Trixie, kernel
`6.18.34+rpt-rpi-v8`, Python 3.13.5, 2026-07-04):

```bash
cd ~/rako-pi
# 1. Compilar el overlay del repo (dtc viene con Raspberry Pi OS).
#    -@ es OBLIGATORIO: genera los __fixups__ para i2s/i2c1/sound/vdd_*_reg
#    que el kernel resuelve al aplicar el overlay contra el árbol base.
dtc -@ -I dts -O dtb -o /tmp/seeed-2mic-voicecard.dtbo \
  hardware/overlays/seeed-2mic-voicecard-micbias-fix.dts

# 2. Instalar el .dtbo.
sudo install -o root -g root -m 0644 /tmp/seeed-2mic-voicecard.dtbo \
  /boot/firmware/overlays/seeed-2mic-voicecard.dtbo

# 3. Smoke test en caliente (opcional pero recomendado, sin reboot):
sudo dtoverlay seeed-2mic-voicecard
aplay -l && arecord -l          # debe aparecer "card N: seeed2micvoicec"

# 4. Persistir en el boot + calibrar + guardar el mixer.
sudo ./scripts/rako-fix-audio-boot     # agrega las líneas a config.txt
./scripts/setup_respeaker_audio.sh     # perfil de captura (amixer)
sudo alsactl store                     # persiste niveles para el reboot
sudo reboot

# 5. Tras el reboot:
./scripts/rako-doctor --full           # captura y playback en verde
```

Notas de la verificación:
- El codec responde en I2C `0x1a` (bus 1) aun sin driver — comprobar con
  `i2cdetect -y 1` (el OLED debe verse en `0x3c`). Si `0x1a` no aparece,
  el problema es de cableado/HAT, no de software.
- Al aplicar el overlay, `dmesg` muestra `wm8960 1-001a` probando; las
  líneas `supply DCVDD/DBVDD/SPKVDD... using dummy regulator` son normales
  (esas supplies opcionales no están en el overlay).
- El warning `memory leak will occur if overlay removed` solo importa si
  se hace `dtoverlay -r` en caliente; en reboot no aplica.
- `rako-fix-audio-boot` agrega `dtoverlay=i2s-mmap`, cuyo `.dtbo` ya no
  existe en kernels 6.x — es inofensivo (solo un warning de boot), pero
  conviene borrar esa línea de `config.txt` para dejarlo limpio.
- Captura de referencia post-calibración: peak ~56%, rms ~5% en ambiente,
  0 muestras clippeadas.

## ReSpeaker — overlay conocido-bueno (verificado 2026-05-10)

Configuración de overlay verificada y funcionando en hardware real (fusionado
desde notas previas de bring-up):

- Overlay fuente: `hardware/overlays/seeed-2mic-voicecard-micbias-fix.dts`
  (incluye la ruta `mclk` de WM8960 y la ruta `"Mic Jack", "MICB"`).
- Instalado como `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo`.
- ALSA card: `seeed2micvoicec`. Dispositivo de captura para scripts de Rako:
  `plughw:seeed2micvoicec,0`.
- Verificado post-reboot: `MICB: On` durante captura; RMS de captura directa
  ~5536, peak ~32250; RMS de captura vía script ~7103, peak ~32757.
- Backup de referencia: `seeed-2mic-voicecard.dtbo.before-seeed-micbias-20260510-005959`.
- El STT puede seguir fallando si el audio clippea o si no se habla con
  claridad en la ventana de captura — `scripts/button_conversation.py`
  normaliza el peak de PCM16 antes de mandar a STT.

### Perfil de captura calibrado

Aplicado y persistido con `alsactl store` vía `scripts/setup_respeaker_audio.sh`:

- `Capture=50`
- `ADC PCM=210`
- `Input Boost LINPUT1/RINPUT1=2`
- `ALC Function=Stereo`
- `ALC Max Gain=6`
- `ALC Target=6`

Resultado de calibración: sin clipping; test final RMS ~10768, peak ~28347,
0 muestras clippeadas.

## Reglas de implementación

- Mantener interfaces mockeables para hardware.
- No bloquear arranque si falta audio output; degradar a fake/log.
- No persistir audio de entrada.
- Tests de hardware real deben ir con marker `hardware` y no correr por defecto.
- Cualquier instalación de drivers HAT/kernel debe pedirse explícitamente antes de ejecutar `sudo` o reiniciar.
