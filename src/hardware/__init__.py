"""Controladores de hardware (GPIO).

Encapsula LEDs (matriz para "ojos", anillo NeoPixel), servos opcionales
(cabeza, orejas), sensores (PIR, táctil capacitivo) y botones físicos
(pánico, emergencia).

Reglas de capa:
- Cada controlador expone una interfaz mockeable; la implementación real
  con `gpiozero`/`adafruit-circuitpython` solo se carga si está corriendo
  en la Pi (detección por arquitectura).
- `orchestrator/` habla a hardware solo a través de las interfaces.
"""
