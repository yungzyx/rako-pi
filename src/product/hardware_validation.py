"""Persisted physical validation checks for a Rako unit."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from db.database import Database

HARDWARE_VALIDATION_KEY = "product.hardware_validation"
HardwareCheckStatus = Literal["pass", "fail"]
HardwareCheckName = Literal[
    "microphone",
    "speaker",
    "oled",
    "button",
    "focus_flow",
    "crisis_bypass",
]


@dataclass(frozen=True, slots=True)
class HardwareCheckRecord:
    name: HardwareCheckName
    status: HardwareCheckStatus
    detail: str
    checked_at: str


@dataclass(frozen=True, slots=True)
class HardwareValidationSummary:
    ready: bool
    required: tuple[HardwareCheckName, ...]
    records: tuple[HardwareCheckRecord, ...]
    missing: tuple[HardwareCheckName, ...]
    failed: tuple[HardwareCheckName, ...]


REQUIRED_HARDWARE_CHECKS: tuple[HardwareCheckName, ...] = (
    "microphone",
    "speaker",
    "oled",
    "button",
    "focus_flow",
    "crisis_bypass",
)


class HardwareValidationService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def summary(self) -> HardwareValidationSummary:
        records = self.list_records()
        latest = {record.name: record for record in records}
        missing = tuple(name for name in REQUIRED_HARDWARE_CHECKS if name not in latest)
        failed = tuple(
            name
            for name in REQUIRED_HARDWARE_CHECKS
            if name in latest and latest[name].status == "fail"
        )
        return HardwareValidationSummary(
            ready=not missing and not failed,
            required=REQUIRED_HARDWARE_CHECKS,
            records=records,
            missing=missing,
            failed=failed,
        )

    def list_records(self) -> tuple[HardwareCheckRecord, ...]:
        raw = self._db.config.get(HARDWARE_VALIDATION_KEY)
        if not raw:
            return ()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return ()
        if not isinstance(payload, list):
            return ()
        records: list[HardwareCheckRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = _hardware_check_name(str(item.get("name", "")))
            if name is None:
                continue
            records.append(
                HardwareCheckRecord(
                    name=name,
                    status="pass" if item.get("status") == "pass" else "fail",
                    detail=_clean_text(item.get("detail", ""), max_len=240),
                    checked_at=_clean_text(item.get("checked_at", ""), max_len=80),
                )
            )
        return tuple(records)

    def record(
        self,
        *,
        name: HardwareCheckName,
        status: HardwareCheckStatus,
        detail: str = "",
        now: datetime | None = None,
    ) -> HardwareValidationSummary:
        clean_name = _hardware_check_name(name)
        if clean_name is None:
            raise ValueError(f"unknown hardware check: {name}")
        records = [record for record in self.list_records() if record.name != clean_name]
        records.append(
            HardwareCheckRecord(
                name=clean_name,
                status=status,
                detail=_clean_text(detail, max_len=240),
                checked_at=_ensure_aware(now or datetime.now(UTC)).isoformat(),
            )
        )
        records.sort(key=lambda record: record.name)
        self._db.config.set(
            HARDWARE_VALIDATION_KEY,
            json.dumps([asdict(record) for record in records], ensure_ascii=False, sort_keys=True),
        )
        return self.summary()


def hardware_check_record_to_dict(record: HardwareCheckRecord) -> dict[str, Any]:
    return asdict(record)


def hardware_validation_summary_to_dict(summary: HardwareValidationSummary) -> dict[str, Any]:
    return {
        "ready": summary.ready,
        "required": list(summary.required),
        "records": [hardware_check_record_to_dict(record) for record in summary.records],
        "missing": list(summary.missing),
        "failed": list(summary.failed),
    }


def _hardware_check_name(value: str) -> HardwareCheckName | None:
    if value in REQUIRED_HARDWARE_CHECKS:
        return value  # type: ignore[return-value]
    return None


def _clean_text(value: object, *, max_len: int) -> str:
    return " ".join(str(value).strip().split())[:max_len]


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
