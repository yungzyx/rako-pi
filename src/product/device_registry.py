"""Local device identity and handoff operations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from config import Settings
from db.database import Database
from product.user_config import PRODUCT_CONFIG_KEYS

DEVICE_IDENTITY_KEY = "product.device_identity"
DEVICE_HEARTBEAT_KEY = "product.device_heartbeat"
_PRESERVED_CONFIG_KEYS = {DEVICE_IDENTITY_KEY, DEVICE_HEARTBEAT_KEY}


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_id: str
    serial: str | None = None
    lot: str | None = None
    assigned_user_label: str | None = None
    provisioned_at: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceHeartbeat:
    at: str
    app_version: str
    status: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ReassignmentResetResult:
    identity: DeviceIdentity
    deleted_config_keys: tuple[str, ...]
    purged_domains: tuple[str, ...]


class DeviceRegistryService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    def get_identity(self) -> DeviceIdentity:
        raw = self._db.config.get(DEVICE_IDENTITY_KEY)
        if raw is not None:
            payload = _decode_json(raw)
            if isinstance(payload, dict) and payload.get("device_id"):
                return DeviceIdentity(
                    device_id=str(payload["device_id"]),
                    serial=_clean_optional_text(payload.get("serial"), max_len=80),
                    lot=_clean_optional_text(payload.get("lot"), max_len=80),
                    assigned_user_label=_clean_optional_text(
                        payload.get("assigned_user_label"), max_len=120
                    ),
                    provisioned_at=_clean_optional_text(payload.get("provisioned_at"), max_len=80),
                )
        device_id = self._settings.rako_device_id or f"rako-{uuid4().hex[:12]}"
        return DeviceIdentity(device_id=device_id)

    def provision(
        self,
        *,
        serial: str | None = None,
        lot: str | None = None,
        assigned_user_label: str | None = None,
        now: datetime | None = None,
    ) -> DeviceIdentity:
        current = asdict(self.get_identity())
        current.update(
            {
                "serial": serial if serial is not None else current.get("serial"),
                "lot": lot if lot is not None else current.get("lot"),
                "assigned_user_label": assigned_user_label
                if assigned_user_label is not None
                else current.get("assigned_user_label"),
            }
        )
        provisioned_at = (
            current.get("provisioned_at") or _ensure_aware(now or datetime.now(UTC)).isoformat()
        )
        identity = DeviceIdentity(
            device_id=_clean_text(current.get("device_id") or "", max_len=80)
            or f"rako-{uuid4().hex[:12]}",
            serial=_clean_optional_text(current.get("serial"), max_len=80),
            lot=_clean_optional_text(current.get("lot"), max_len=80),
            assigned_user_label=_clean_optional_text(
                current.get("assigned_user_label"), max_len=120
            ),
            provisioned_at=provisioned_at,
        )
        self._set_json(DEVICE_IDENTITY_KEY, asdict(identity))
        return identity

    def heartbeat(
        self,
        *,
        app_version: str,
        status: str = "ok",
        detail: str | None = None,
        now: datetime | None = None,
    ) -> DeviceHeartbeat:
        heartbeat = DeviceHeartbeat(
            at=_ensure_aware(now or datetime.now(UTC)).isoformat(),
            app_version=_clean_text(app_version, max_len=40),
            status=_clean_text(status, max_len=40) or "ok",
            detail=_clean_optional_text(detail, max_len=240),
        )
        self._set_json(DEVICE_HEARTBEAT_KEY, asdict(heartbeat))
        return heartbeat

    def get_heartbeat(self) -> DeviceHeartbeat | None:
        payload = _decode_json(self._db.config.get(DEVICE_HEARTBEAT_KEY))
        if not isinstance(payload, dict):
            return None
        at = payload.get("at")
        app_version = payload.get("app_version")
        status = payload.get("status")
        if (
            not isinstance(at, str)
            or not isinstance(app_version, str)
            or not isinstance(status, str)
        ):
            return None
        return DeviceHeartbeat(
            at=at,
            app_version=app_version,
            status=status,
            detail=_clean_optional_text(payload.get("detail"), max_len=240),
        )

    def reset_for_reassignment(self) -> ReassignmentResetResult:
        identity = self.get_identity()
        heartbeat = self.get_heartbeat()
        deleted_keys: list[str] = []
        for key in tuple(self._db.config.get_all()):
            if key in _PRESERVED_CONFIG_KEYS:
                continue
            if (
                key in PRODUCT_CONFIG_KEYS or key.startswith(("whatsapp.", "mobile."))
            ) and self._db.config.delete(key):
                deleted_keys.append(key)
        self._db.tasks.purge_all()
        self._db.interactions.purge_all()
        self._db.emotional_states.purge_all()
        self._db.achievements.purge_all()
        self._set_json(DEVICE_IDENTITY_KEY, asdict(identity))
        if heartbeat is not None:
            self._set_json(DEVICE_HEARTBEAT_KEY, asdict(heartbeat))
        return ReassignmentResetResult(
            identity=identity,
            deleted_config_keys=tuple(sorted(deleted_keys)),
            purged_domains=("tasks", "interactions", "emotional_states", "achievements"),
        )

    def _set_json(self, key: str, payload: object) -> None:
        self._db.config.set(key, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def device_identity_to_dict(identity: DeviceIdentity) -> dict[str, Any]:
    return asdict(identity)


def device_heartbeat_to_dict(heartbeat: DeviceHeartbeat | None) -> dict[str, Any] | None:
    return asdict(heartbeat) if heartbeat is not None else None


def reassignment_reset_to_dict(result: ReassignmentResetResult) -> dict[str, Any]:
    return {
        "identity": device_identity_to_dict(result.identity),
        "deleted_config_keys": list(result.deleted_config_keys),
        "purged_domains": list(result.purged_domains),
    }


def _decode_json(raw: str | None) -> object:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _clean_optional_text(value: object, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = _clean_text(value, max_len=max_len)
    return text or None


def _clean_text(value: object, *, max_len: int) -> str:
    return " ".join(str(value).strip().split())[:max_len]


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
