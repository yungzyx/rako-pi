"""Configuración de SQLCipher.

Inicializa la conexión con la clave del .env, valida el cifrado al
arranque y maneja la rotación de la clave (procedimiento documentado).
La clave nunca se imprime ni se persiste fuera del .env.
"""
