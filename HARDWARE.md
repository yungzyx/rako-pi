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
