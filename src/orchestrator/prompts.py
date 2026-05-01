"""Construcción de prompts para Claude.

Carga el system prompt base (espejo de `../Rako-kb/system_prompt_rako.md`),
inyecta los chunks del RAG y el contexto mínimo anonimizado del usuario.
Anonimiza nombres y locaciones antes de enviar a la API.
"""
