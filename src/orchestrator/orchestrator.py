"""Bucle principal de decisión por turno.

Punto de entrada `handle_turn(user_input)`:
- Chequea `safety.detect_crisis()`. Si dispara, ejecuta protocolo curado.
- Recupera contexto del usuario desde `db/`.
- Llama al RAG y al LLM.
- Despacha la respuesta a hardware + sync.
"""
