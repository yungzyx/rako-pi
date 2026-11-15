# Contribuir a Rako

[Volver al proyecto](README.md) · [Guía de desarrollo](docs/DEVELOPMENT.md)

## Preparar el entorno

Usa Python 3.12 o superior e instala `requirements-dev.txt` siguiendo la [guía de desarrollo](docs/DEVELOPMENT.md). Los tests usan simulaciones de hardware y servicios cloud, sin credenciales reales.

Antes de modificar el comportamiento, lee [AGENTS.md](AGENTS.md) y las restricciones de privacidad y seguridad de [CLAUDE.md](CLAUDE.md).

## Proponer un cambio

1. Crea una rama con un nombre descriptivo.
2. Mantén el cambio centrado en un problema. Si modifica comportamiento, añade una prueba que reproduzca el caso.
3. Ejecuta los controles desde la raíz del repositorio:

   ```bash
   python scripts/checks.py lint
   python scripts/checks.py test
   python scripts/checks.py safety
   python scripts/checks.py hygiene
   ```

4. Usa commits en inglés con prefijos como `docs:`, `fix:`, `feat:` o `test:`.
5. Abre un pull request explicando el problema, el resultado, la validación y cualquier cambio en el tratamiento de datos. Para cambios visuales, incluye una captura.

## Datos y seguridad

No incluyas `.env`, credenciales, bases de datos, audio de usuarios ni historiales personales en commits o capturas. Utiliza datos sintéticos para reproducir problemas.

Las rutas de crisis deben seguir evitando el LLM. Los cambios en proveedores, memoria o canales deben documentar qué datos salen del dispositivo. Consulta las [reglas completas](CLAUDE.md#41-privacidad).

## Documentación e imágenes

Mantén el README como entrada al proyecto y coloca los detalles técnicos en `docs/`. Guarda las imágenes en `docs/assets/`, añade texto alternativo y registra su procedencia. Distingue capturas reales, renders y propuestas futuras.

Comprueba que los enlaces relativos funcionen en GitHub y que las instrucciones puedan seguirse desde una clonación limpia. La [licencia del proyecto](README.md#licencia) sigue pendiente de definición.
