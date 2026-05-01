"""Detección emocional (SER local + análisis de patrones).

Procesa audio crudo del usuario *antes* de enviarlo a STT cloud y produce
un vector de emoción (valencia, activación, dominancia) que alimenta al
orquestador. Complementa con análisis de patrones (latencia, hora del
día, completitud de tareas).

Restricción crítica: el vector emocional crudo y el audio NUNCA salen de
la Pi. El historial de estados emocionales vive en SQLite local cifrado.

Modelo principal: Wav2Vec2 fine-tuneado para emoción (cuantizado para
Pi 4). Configurable vía SER_MODEL en .env.
"""
