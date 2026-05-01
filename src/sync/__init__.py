"""Cliente de sincronización con Firebase.

Lo que se sincroniza:
- Tareas creadas en la app → Pi las consume.
- Eventos no sensibles que la Pi emite (logros, panic_button, etc.).
- Configuración del usuario.
- Notificaciones push hacia la app vía FCM.

Lo que NO se sincroniza (jamás):
- Audio crudo.
- Transcripciones completas.
- Vectores emocionales detallados.
- Identidad real del usuario más allá de un opaque ID.

Si pierde internet, encola localmente y reintenta al volver.
"""
