from __future__ import annotations

from db.database import Database
from product.hardware_validation import (
    HardwareValidationService,
    hardware_validation_summary_to_dict,
)


def test_hardware_validation_tracks_missing_and_failed_checks(db_conn) -> None:
    service = HardwareValidationService(Database(db_conn))

    initial = service.summary()
    failed = service.record(name="microphone", status="fail", detail="clipping")

    assert initial.ready is False
    assert "microphone" in initial.missing
    assert failed.ready is False
    assert failed.failed == ("microphone",)


def test_hardware_validation_ready_when_all_required_pass(db_conn) -> None:
    service = HardwareValidationService(Database(db_conn))

    for name in service.summary().required:
        summary = service.record(name=name, status="pass", detail="ok")

    payload = hardware_validation_summary_to_dict(summary)

    assert payload["ready"] is True
    assert payload["missing"] == []
    assert payload["failed"] == []
    assert len(payload["records"]) == 6
