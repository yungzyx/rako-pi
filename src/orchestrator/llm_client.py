"""Cliente de Anthropic Claude.

Wrapper sobre `anthropic` con:
- Reintentos con backoff (tenacity).
- Timeouts agresivos para mantener la latencia objetivo (3-5s end-to-end).
- Modo no-training verificado en headers/configuración.
- Cache de respuestas comunes (mitigación de costos).
"""
