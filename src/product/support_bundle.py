"""Sanitized support bundle for deployed Rako devices."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import Settings
from db.database import Database
from product.fleet_snapshot import build_fleet_snapshot, fleet_snapshot_to_dict
from product.update_status import current_app_version

SECRET_FIELD_NAMES = (
    "api_key",
    "access_token",
    "app_secret",
    "token",
    "password",
    "encryption_key",
    "credentials",
)


@dataclass(frozen=True, slots=True)
class SupportBundle:
    generated_at: str
    app_version: str
    device_id: str
    snapshot: dict[str, Any]
    env_presence: dict[str, bool]
    local_paths: dict[str, str]
    notes: tuple[str, ...]


def build_support_bundle(
    db: Database,
    settings: Settings,
    *,
    app_version: str | None = None,
    now: datetime | None = None,
) -> SupportBundle:
    version = app_version or current_app_version()
    snapshot = fleet_snapshot_to_dict(build_fleet_snapshot(db, settings, app_version=version))
    device_id = str(snapshot["device_id"])
    return SupportBundle(
        generated_at=_ensure_aware(now or datetime.now(UTC)).isoformat(),
        app_version=version,
        device_id=device_id,
        snapshot=_sanitize(snapshot),
        env_presence=_env_presence(settings),
        local_paths={
            "sqlite_path": settings.sqlite_path,
            "chroma_db_path": settings.chroma_db_path,
            "obsidian_vault_path": settings.obsidian_vault_path,
        },
        notes=(
            "No raw transcripts, WiFi passwords, API keys, or editable memory text are included.",
            "Share this bundle with support when a deployed device is hard to diagnose.",
        ),
    )


def support_bundle_to_dict(bundle: SupportBundle) -> dict[str, Any]:
    return {
        "generated_at": bundle.generated_at,
        "app_version": bundle.app_version,
        "device_id": bundle.device_id,
        "snapshot": bundle.snapshot,
        "env_presence": bundle.env_presence,
        "local_paths": bundle.local_paths,
        "notes": list(bundle.notes),
    }


def write_support_bundle_json(bundle: SupportBundle, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(support_bundle_to_dict(bundle), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _env_presence(settings: Settings) -> dict[str, bool]:
    return {
        "rako_api_token": bool(settings.rako_api_token),
        "sqlite_encryption_key": bool(settings.sqlite_encryption_key),
        "openai_api_key": bool(settings.openai_api_key),
        "anthropic_api_key": bool(settings.anthropic_api_key),
        "google_application_credentials": bool(settings.google_application_credentials),
        "elevenlabs_api_key": bool(settings.elevenlabs_api_key),
        "whatsapp_cloud_access_token": bool(settings.whatsapp_cloud_access_token),
        "whatsapp_cloud_app_secret": bool(settings.whatsapp_cloud_app_secret),
        "firebase_credentials_path": bool(settings.firebase_credentials_path),
    }


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(secret in key_text for secret in SECRET_FIELD_NAMES):
                sanitized[key] = "<redacted>" if item else None
            elif key == "memory":
                sanitized[key] = "<redacted>"
            else:
                sanitized[key] = _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
