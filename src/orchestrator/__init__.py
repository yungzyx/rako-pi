"""Orquestador IA — pieza central de decisión.

Recibe inputs (texto transcrito, vector emocional, estado del usuario en
SQLite, evento del hardware) y decide qué hace el robot:

1. Consulta a `safety/` PRIMERO. Si hay señal de crisis, bypass al LLM.
2. Consulta al RAG (`rag/`) con la situación combinada.
3. Construye prompt para Claude (system prompt + chunks + contexto
   anonimizado) y llama a la API.
4. Despacha la respuesta: TTS, LEDs, motores, evento a Firebase.
5. Persiste el intercambio en SQLite (excepto en modo privado).

Reglas de capa:
- Depende de `safety`, `rag`, `db`, `voice`, `hardware`, `sync`.
- NUNCA salta `safety`.
- Mantener stateless por turno; el estado vive en `db/`.
"""
