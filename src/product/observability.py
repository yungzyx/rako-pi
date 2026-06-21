"""Local observability snapshot for a deployed Rako."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from config import Settings
from db.database import Database

ServiceStatus = Literal["ready", "disabled", "blocked", "unknown"]


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    name: str
    status: ServiceStatus
    detail: str


@dataclass(frozen=True, slots=True)
class ObservabilitySnapshot:
    generated_at: str
    services: tuple[ServiceHealth, ...]
    sync_pending: int
    sync_last_error: str | None
    log_files: tuple[str, ...]
    operator_notes: tuple[str, ...]


def build_observability_snapshot(
    db: Database,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> ObservabilitySnapshot:
    return ObservabilitySnapshot(
        generated_at=_ensure_aware(now or datetime.now(UTC)).isoformat(),
        services=_service_health(settings),
        sync_pending=_sync_pending(db),
        sync_last_error=_sync_last_error(db),
        log_files=_log_files(Path("logs")),
        operator_notes=(
            "Use journalctl -u rako-api -n 80 and journalctl -u rako-chat -n 80 for service logs.",
            "Support bundles redact secrets and user memory; do not paste raw transcripts into tickets.",
        ),
    )


def observability_snapshot_to_dict(snapshot: ObservabilitySnapshot) -> dict[str, Any]:
    return {
        "generated_at": snapshot.generated_at,
        "services": [asdict(service) for service in snapshot.services],
        "sync_pending": snapshot.sync_pending,
        "sync_last_error": snapshot.sync_last_error,
        "log_files": list(snapshot.log_files),
        "operator_notes": list(snapshot.operator_notes),
    }


def _service_health(settings: Settings) -> tuple[ServiceHealth, ...]:
    return (
        ServiceHealth(
            "local api", "ready" if settings.rako_api_token else "disabled", _token_detail(settings)
        ),
        ServiceHealth(
            "database", "ready" if settings.sqlite_path else "blocked", settings.sqlite_path
        ),
        ServiceHealth("stt", "ready" if _stt_ready(settings) else "blocked", settings.stt_provider),
        ServiceHealth("tts", "ready" if _tts_ready(settings) else "blocked", settings.tts_provider),
        ServiceHealth(
            "whatsapp",
            "ready" if _whatsapp_ready(settings) else "disabled",
            settings.whatsapp_client,
        ),
        ServiceHealth(
            "ota",
            "ready" if settings.rako_update_manifest_path else "disabled",
            settings.rako_release_channel,
        ),
    )


def _token_detail(settings: Settings) -> str:
    if settings.rako_api_token:
        return "token configured"
    if settings.rako_env == "dev":
        return "dev mode permits missing token"
    return "missing RAKO_API_TOKEN"


def _stt_ready(settings: Settings) -> bool:
    return (settings.stt_provider == "openai_whisper" and bool(settings.openai_api_key)) or (
        settings.stt_provider == "google" and bool(settings.google_application_credentials)
    )


def _tts_ready(settings: Settings) -> bool:
    return (settings.tts_provider == "elevenlabs" and bool(settings.elevenlabs_api_key)) or (
        settings.tts_provider == "google" and bool(settings.google_application_credentials)
    )


def _whatsapp_ready(settings: Settings) -> bool:
    if settings.whatsapp_client == "memory":
        return True
    return bool(settings.whatsapp_cloud_access_token and settings.whatsapp_cloud_phone_number_id)


def _sync_pending(db: Database) -> int:
    row = db._conn.execute("SELECT COUNT(*) AS count FROM sync_queue").fetchone()
    return int(row["count"])


def _sync_last_error(db: Database) -> str | None:
    row = db._conn.execute(
        """
        SELECT last_error
        FROM sync_queue
        WHERE last_error IS NOT NULL
        ORDER BY attempts DESC, created_at DESC
        LIMIT 1
        """
    ).fetchone()
    return str(row["last_error"]) if row and row["last_error"] else None


def _log_files(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    return tuple(str(item) for item in sorted(path.glob("*.log"))[:20])


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
