"""Detección proactiva de bloqueo.

Job periódico que consulta `emotion/patterns.py` y, al cruzar un umbral,
inicia un turno suave: LEDs en pulso lento, voz baja, una sola pregunta.
Si el usuario no responde, desescala (no insiste).

Ver Arquitectura §4.2.
"""
