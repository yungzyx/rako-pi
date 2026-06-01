"""FastAPI adapter for the Rako mobile app.

Run locally on the Pi:

    PYTHONPATH=src uvicorn mobile.api:create_app --factory --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from config import Settings
from db.database import Database
from mobile.service import MobileService, focus_start_to_dict, status_to_dict


class StartFocusRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    minutes: int = Field(default=25, ge=1, le=180)


def create_app() -> Any:
    try:
        from fastapi import Depends, FastAPI
    except ImportError as exc:  # pragma: no cover - depends on optional HTTP deps
        raise RuntimeError("Install fastapi and uvicorn to run the mobile API") from exc

    settings = Settings()
    app = FastAPI(title="Rako Local API", version="0.1.0")

    async def build_service() -> AsyncIterator[MobileService]:
        db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
        try:
            yield MobileService(db)
        finally:
            db.close()

    service_dep = Depends(build_service)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    async def status(service: MobileService = service_dep) -> dict[str, Any]:
        return status_to_dict(service.status())

    @app.post("/focus/start")
    async def start_focus(
        request: StartFocusRequest,
        service: MobileService = service_dep,
    ) -> dict[str, Any]:
        return focus_start_to_dict(
            service.start_focus(title=request.title, minutes=request.minutes)
        )

    @app.post("/focus/cancel")
    async def cancel_focus(service: MobileService = service_dep) -> dict[str, bool]:
        return {"cancelled": service.cancel_focus()}

    return app
