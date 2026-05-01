"""Protocolo de manejo de crisis.

Este módulo es el más sensible del sistema. Reglas:

1. El LLM se BYPASSEA en crisis. Cero generación.
2. Las respuestas son pre-curadas por profesionales y se cargan
   estáticamente desde `responses.py` y `prerecorded/`.
3. Disparadores: palabras clave de ideación/autolesión, vector emocional
   extremo sostenido, botón pánico (físico o app), inactividad anormal
   tras alta angustia previa.
4. Acciones: presencia (no soluciones) → activar contacto de confianza
   con consentimiento previo → recursos de derivación → registro privado.
5. NO hace: diagnosticar, prometer confidencialidad absoluta, reemplazar
   ayuda profesional, frases motivacionales.
6. Tests de fixtures de crisis deben pasar SIEMPRE en CI. Si fallan,
   bloquear el merge.

Ver Arquitectura §7.
"""
