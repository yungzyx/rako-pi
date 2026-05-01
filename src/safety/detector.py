"""Detector de señales de crisis.

Combina:
- Lista curada de palabras clave (mantener fuera del repo público
  posible exfiltración? Documentar política).
- Reglas sobre el vector emocional (umbrales sostenidos en el tiempo).
- Eventos explícitos: botón pánico físico o app.

Devuelve un `CrisisSignal` inmutable con nivel y motivo. El orquestador
debe consultarlo ANTES de cualquier llamada al LLM.
"""
