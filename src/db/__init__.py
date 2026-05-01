"""Estado del usuario en SQLite local cifrado (SQLCipher).

Almacena tareas, historial de interacciones, estados emocionales,
logros y configuración. NUNCA sale de la Pi.

Tablas (ver Arquitectura §5.1):
- `tasks`
- `interactions`
- `emotional_states`
- `achievements`
- `user_config`

Encriptación obligatoria. La clave se carga de `SQLITE_ENCRYPTION_KEY`
y NO se loggea jamás.
"""
