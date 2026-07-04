"""Routers por dominio de la API móvil."""

from __future__ import annotations

from fastapi import APIRouter

from mobile.routes import core, device, factory, setup, user, whatsapp


def all_routers() -> tuple[APIRouter, ...]:
    return (
        core.router,
        user.router,
        setup.router,
        factory.router,
        device.router,
        whatsapp.router,
    )
