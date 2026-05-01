"""Detector de palabra de activación.

Escucha continuamente el micrófono buscando "Hey Rako", "Hola Rako" u
"Oye Rako". También acepta activación por presión sobre el cuerpo del
robot (ver `hardware/touch.py`). Cuando dispara, abre una ventana de
captura para STT.

Procesamiento 100% local. Diseñado para correr con bajo consumo de CPU
en la Pi 4.
"""
