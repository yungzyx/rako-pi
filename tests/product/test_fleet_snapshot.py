from __future__ import annotations

from config import Settings
from db.database import Database
from product.device_registry import DeviceRegistryService
from product.fleet_snapshot import build_fleet_snapshot, fleet_snapshot_to_dict


def test_fleet_snapshot_collects_device_factory_security_and_hardware(db_conn) -> None:
    db = Database(db_conn)
    settings = Settings(
        _env_file=None,
        rako_env="prod",
        rako_device_id="rako-001",
        rako_api_token="local-token",
    )
    DeviceRegistryService(db, settings).provision(
        serial="SN-001",
        lot="pilot-a",
        assigned_user_label="nico@udd",
    )
    DeviceRegistryService(db, settings).heartbeat(app_version="0.1.0", status="ok")

    snapshot = build_fleet_snapshot(db, settings, app_version="0.1.0")
    payload = fleet_snapshot_to_dict(snapshot)

    assert payload["device_id"] == "rako-001"
    assert payload["online"] is True
    assert payload["assignment"] == "nico@udd"
    assert "factory" in payload
    assert "security" in payload
    assert "hardware" in payload
