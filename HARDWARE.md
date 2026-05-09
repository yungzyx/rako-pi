# Rako Pi — Hardware actual

Fecha de actualización: 2026-05-09

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

- Pantalla OLED por I2C.
- Uso esperado:
  - estados breves: escuchando, pensando, hablando, error, crisis/protocolo, offline;
  - no depender solo de LEDs/voz para feedback.
- Pendiente técnico:
  - confirmar modelo/resolución/controlador exacto, por ejemplo SSD1306 128x64 o similar;
  - confirmar dirección I2C con `i2cdetect -y 1` cuando se haga prueba física.

## Reglas de implementación

- Mantener interfaces mockeables para hardware.
- No bloquear arranque si falta audio output; degradar a fake/log.
- No persistir audio de entrada.
- Tests de hardware real deben ir con marker `hardware` y no correr por defecto.
- Cualquier instalación de drivers HAT/kernel debe pedirse explícitamente antes de ejecutar `sudo` o reiniciar.
