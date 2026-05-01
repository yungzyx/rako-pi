"""Cliente Firebase (Auth + Firestore + FCM).

Wrapper sobre `firebase-admin` con:
- Verificación al arranque de que las reglas correctas están desplegadas.
- Cola local para reintentos cuando no hay red.
- Sanitización del payload antes de subir (drop de campos sensibles).
"""
