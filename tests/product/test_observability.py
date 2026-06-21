from __future__ import annotations

from datetime import UTC, datetime

from config import Settings
from db.database import Database
from product.observability import build_observability_snapshot, observability_snapshot_to_dict
from sync.queue import SyncQueue
from sync.types import SyncEvent, SyncEventKind


def test_observability_reports_services_and_sync_error(db_conn) -> None:
    db = Database(db_conn)
    queue = SyncQueue(db._conn)
    event = SyncEvent(
        id="evt-1",
        kind=SyncEventKind.TASK_CREATED_FROM_VOICE,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload={"title": "calculo"},
    )
    queue.enqueue(event)
    queued = queue.list_pending()[0]
    queue.mark_failed(queued, error="network down")

    snapshot = build_observability_snapshot(
        db,
        Settings(_env_file=None, rako_device_id="rako-001", whatsapp_client="memory"),
    )
    payload = observability_snapshot_to_dict(snapshot)

    assert payload["sync_pending"] == 1
    assert payload["sync_last_error"] == "network down"
    assert any(service["name"] == "whatsapp" for service in payload["services"])
