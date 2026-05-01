"""Análisis de patrones de comportamiento.

Reglas + clasificador liviano sobre señales no-acústicas:
tiempo desde la última interacción, hora del día, tareas pendientes,
completitud reciente, latencia de respuesta. Produce una señal de
"posible bloqueo" que alimenta al orquestador para la detección
proactiva (ver Arquitectura §4.2).
"""
