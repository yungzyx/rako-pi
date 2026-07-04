"""FastAPI adapter for the Rako mobile app.

Ensambla la app desde los routers por dominio (`mobile/routes/`) y las
dependencias compartidas (`mobile/deps.py`). La configuración vive en
`app.state` — los routers no cargan `.env` por su cuenta.

Run locally on the Pi:

    PYTHONPATH=src uvicorn mobile.api:create_app --factory --host 127.0.0.1 --port 8765

Documentación interactiva (para el desarrollo de la app Flutter):
/docs (Swagger UI) y /openapi.json — exportable con
`python scripts/export_openapi.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from config import Settings
from db.database import Database
from product.update_status import current_app_version

_OPENAPI_DESCRIPTION = (
    "API local del cerebro Rako (Raspberry Pi). Pensada para la app móvil "
    "Flutter en la misma red. Autenticación: `Authorization: Bearer "
    "<RAKO_API_TOKEN>` en todo excepto /health, /pairing/info y las páginas "
    "HTML de setup/factory."
)


def create_app() -> Any:
    try:
        from fastapi import FastAPI
    except ImportError as exc:  # pragma: no cover - depends on optional HTTP deps
        raise RuntimeError("Install fastapi and uvicorn to run the mobile API") from exc

    # Los routers importan fastapi a nivel de módulo, así que solo se
    # cargan una vez confirmada la dependencia opcional.
    from mobile.routes import all_routers

    settings = Settings()
    app_version = current_app_version()

    @asynccontextmanager
    async def _lifespan(_app: Any) -> AsyncIterator[None]:
        # CLAUDE.md §4.1.6: fuera de dev, la API no debe aceptar tráfico si
        # la base local no está cifrada (SQLCipher). `TestClient(app)` sin
        # `with` no dispara lifespan, así que esto no afecta tests que
        # construyen la app sin entrar al context manager.
        if settings.rako_env != "dev":
            probe = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
            try:
                probe.require_encrypted()
            finally:
                probe.close()
        yield

    app = FastAPI(
        title="Rako Local API",
        version=app_version,
        description=_OPENAPI_DESCRIPTION,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.app_version = app_version
    for router in all_routers():
        app.include_router(router)
    return app
