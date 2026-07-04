"""User-owned product configuration.

This layer stores the pieces a mobile app needs to make one physical Rako safe
for a specific user: profile, consent, external channels, and editable memory.
It intentionally uses the local `user_config` key/value store so the MVP can add
product onboarding without a schema migration.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from db.database import Database

PROFILE_KEY = "product.user_profile"
CONSENT_KEY = "product.privacy_consent"
CHANNELS_KEY = "product.channels"
MEMORY_KEY = "product.editable_memory"
PRODUCT_CONFIG_KEYS = (PROFILE_KEY, CONSENT_KEY, CHANNELS_KEY, MEMORY_KEY)

MemoryCategory = Literal["study", "routine", "motivation", "preference", "boundary"]
MemorySensitivity = Literal["normal", "sensitive"]


@dataclass(frozen=True, slots=True)
class UserProfile:
    preferred_name: str | None = None
    university: str | None = None
    program: str | None = None
    timezone: str = "America/Santiago"
    locale: str = "es-CL"


@dataclass(frozen=True, slots=True)
class PrivacyConsent:
    whatsapp_enabled: bool = False
    proactive_messages_enabled: bool = False
    progress_reports_enabled: bool = False
    sensitive_memory_enabled: bool = False
    wellbeing_escalation_enabled: bool = False
    # Alerta al contacto de confianza cuando se activa el protocolo de
    # crisis (CLAUDE.md §4.2.3). Off por defecto: requiere consentimiento
    # explícito registrado durante el onboarding.
    trusted_contact_alerts_enabled: bool = False
    accepted_at: str | None = None


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    whatsapp_number: str | None = None
    trusted_contact_name: str | None = None
    trusted_contact_phone: str | None = None
    wellbeing_unit_name: str | None = None
    wellbeing_unit_phone: str | None = None
    wifi_ssid: str | None = None


@dataclass(frozen=True, slots=True)
class EditableMemory:
    id: str
    category: MemoryCategory
    text: str
    sensitivity: MemorySensitivity
    created_at: str


@dataclass(frozen=True, slots=True)
class OnboardingStatus:
    ready: bool
    missing: tuple[str, ...]
    profile: UserProfile
    consent: PrivacyConsent
    channels: ChannelConfig
    memory_count: int


class UserConfigService:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_profile(self) -> UserProfile:
        return _decode_dataclass(self._db.config.get(PROFILE_KEY), UserProfile)

    def update_profile(self, patch: dict[str, Any]) -> UserProfile:
        current = asdict(self.get_profile())
        current.update(_clean_patch(patch))
        profile = UserProfile(
            preferred_name=_clean_optional_text(current.get("preferred_name"), max_len=80),
            university=_clean_optional_text(current.get("university"), max_len=120),
            program=_clean_optional_text(current.get("program"), max_len=120),
            timezone=_clean_text(current.get("timezone") or "America/Santiago", max_len=64),
            locale=_clean_text(current.get("locale") or "es-CL", max_len=16),
        )
        self._set_json(PROFILE_KEY, asdict(profile))
        return profile

    def get_consent(self) -> PrivacyConsent:
        return _decode_dataclass(self._db.config.get(CONSENT_KEY), PrivacyConsent)

    def update_consent(
        self, patch: dict[str, Any], *, now: datetime | None = None
    ) -> PrivacyConsent:
        current = asdict(self.get_consent())
        current.update(_clean_patch(patch))
        any_enabled = any(
            bool(current.get(key))
            for key in (
                "whatsapp_enabled",
                "proactive_messages_enabled",
                "progress_reports_enabled",
                "sensitive_memory_enabled",
                "wellbeing_escalation_enabled",
                "trusted_contact_alerts_enabled",
            )
        )
        accepted_at = current.get("accepted_at")
        if any_enabled and not accepted_at:
            accepted_at = _ensure_aware(now or datetime.now(UTC)).isoformat()
        consent = PrivacyConsent(
            whatsapp_enabled=bool(current.get("whatsapp_enabled")),
            proactive_messages_enabled=bool(current.get("proactive_messages_enabled")),
            progress_reports_enabled=bool(current.get("progress_reports_enabled")),
            sensitive_memory_enabled=bool(current.get("sensitive_memory_enabled")),
            wellbeing_escalation_enabled=bool(current.get("wellbeing_escalation_enabled")),
            trusted_contact_alerts_enabled=bool(current.get("trusted_contact_alerts_enabled")),
            accepted_at=str(accepted_at) if accepted_at else None,
        )
        self._set_json(CONSENT_KEY, asdict(consent))
        return consent

    def get_channels(self) -> ChannelConfig:
        return _decode_dataclass(self._db.config.get(CHANNELS_KEY), ChannelConfig)

    def update_channels(self, patch: dict[str, Any]) -> ChannelConfig:
        if "wifi_password" in patch:
            raise ValueError("wifi_password must not be stored in Rako local config")
        current = asdict(self.get_channels())
        current.update(_clean_patch(patch))
        channels = ChannelConfig(
            whatsapp_number=_clean_optional_text(current.get("whatsapp_number"), max_len=32),
            trusted_contact_name=_clean_optional_text(
                current.get("trusted_contact_name"), max_len=120
            ),
            trusted_contact_phone=_clean_optional_text(
                current.get("trusted_contact_phone"), max_len=32
            ),
            wellbeing_unit_name=_clean_optional_text(
                current.get("wellbeing_unit_name"), max_len=160
            ),
            wellbeing_unit_phone=_clean_optional_text(
                current.get("wellbeing_unit_phone"), max_len=32
            ),
            wifi_ssid=_clean_optional_text(current.get("wifi_ssid"), max_len=64),
        )
        self._set_json(CHANNELS_KEY, asdict(channels))
        return channels

    def list_memory(self) -> tuple[EditableMemory, ...]:
        raw_items = _decode_json(self._db.config.get(MEMORY_KEY), default=[])
        if not isinstance(raw_items, list):
            return ()
        memories: list[EditableMemory] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            memories.append(
                EditableMemory(
                    id=str(item.get("id", "")),
                    category=_memory_category(str(item.get("category", "preference"))),
                    text=_clean_text(item.get("text", ""), max_len=240),
                    sensitivity=_memory_sensitivity(str(item.get("sensitivity", "normal"))),
                    created_at=str(item.get("created_at", "")),
                )
            )
        return tuple(memory for memory in memories if memory.id and memory.text)

    def add_memory(
        self,
        *,
        text: str,
        category: MemoryCategory = "preference",
        sensitivity: MemorySensitivity = "normal",
        now: datetime | None = None,
    ) -> EditableMemory:
        clean_text = _clean_text(text, max_len=240)
        clean_category = _memory_category(str(category))
        clean_sensitivity = _memory_sensitivity(str(sensitivity))
        if not clean_text:
            raise ValueError("memory text cannot be empty")
        if clean_sensitivity == "sensitive" and not self.get_consent().sensitive_memory_enabled:
            raise ValueError("sensitive memory requires explicit consent")
        memory = EditableMemory(
            id=f"mem_{uuid4().hex}",
            category=clean_category,
            text=clean_text,
            sensitivity=clean_sensitivity,
            created_at=_ensure_aware(now or datetime.now(UTC)).isoformat(),
        )
        memories = (*self.list_memory(), memory)
        self._set_json(MEMORY_KEY, [asdict(item) for item in memories[-100:]])
        return memory

    def delete_memory(self, id: str) -> bool:
        current = self.list_memory()
        kept = tuple(memory for memory in current if memory.id != id)
        if len(kept) == len(current):
            return False
        self._set_json(MEMORY_KEY, [asdict(item) for item in kept])
        return True

    def export_user_data(self) -> dict[str, Any]:
        """Return the user-owned product data, without secrets or raw logs."""

        status = self.onboarding_status()
        return {
            "profile": user_profile_to_dict(status.profile),
            "consent": consent_to_dict(status.consent),
            "channels": channels_to_dict(status.channels),
            "memory": [memory_to_dict(item) for item in self.list_memory()],
            "onboarding": onboarding_status_to_dict(status),
        }

    def delete_user_data(self) -> dict[str, bool]:
        """Rako's full data wipe: profile, consent, channels, editable memory,
        AND all local history — tasks, interactions, mood samples, achievements,
        crisis journal (CLAUDE.md §4.1.5: "borrado total ... efecto inmediato").
        """

        existed = {key: self._db.config.get(key) is not None for key in PRODUCT_CONFIG_KEYS}
        self._db.purge_all_user_data()
        return existed

    def onboarding_status(self) -> OnboardingStatus:
        profile = self.get_profile()
        consent = self.get_consent()
        channels = self.get_channels()
        missing: list[str] = []
        if not profile.preferred_name:
            missing.append("preferred_name")
        if not channels.wifi_ssid:
            missing.append("wifi_ssid")
        if self._db.config.get(CONSENT_KEY) is None:
            missing.append("privacy_consent")
        if consent.whatsapp_enabled and not channels.whatsapp_number:
            missing.append("whatsapp_number")
        if consent.wellbeing_escalation_enabled and not channels.wellbeing_unit_phone:
            missing.append("wellbeing_unit_phone")
        return OnboardingStatus(
            ready=not missing,
            missing=tuple(missing),
            profile=profile,
            consent=consent,
            channels=channels,
            memory_count=len(self.list_memory()),
        )

    def whatsapp_can_send(self) -> bool:
        consent = self.get_consent()
        channels = self.get_channels()
        return consent.whatsapp_enabled and bool(channels.whatsapp_number)

    def progress_reports_can_send(self) -> bool:
        consent = self.get_consent()
        return self.whatsapp_can_send() and consent.progress_reports_enabled

    def proactive_messages_can_send(self) -> bool:
        consent = self.get_consent()
        return self.whatsapp_can_send() and consent.proactive_messages_enabled

    def _set_json(self, key: str, payload: object) -> None:
        self._db.config.set(key, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def user_profile_to_dict(profile: UserProfile) -> dict[str, Any]:
    return asdict(profile)


def consent_to_dict(consent: PrivacyConsent) -> dict[str, Any]:
    return asdict(consent)


def channels_to_dict(channels: ChannelConfig) -> dict[str, Any]:
    return asdict(channels)


def memory_to_dict(memory: EditableMemory) -> dict[str, Any]:
    return asdict(memory)


def onboarding_status_to_dict(status: OnboardingStatus) -> dict[str, Any]:
    return {
        "ready": status.ready,
        "missing": list(status.missing),
        "profile": user_profile_to_dict(status.profile),
        "consent": consent_to_dict(status.consent),
        "channels": channels_to_dict(status.channels),
        "memory_count": status.memory_count,
    }


def _decode_dataclass(raw: str | None, cls):
    payload = _decode_json(raw, default={})
    if not isinstance(payload, dict):
        payload = {}
    return cls(**{key: value for key, value in payload.items() if key in cls.__dataclass_fields__})


def _decode_json(raw: str | None, *, default: object) -> object:
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _clean_patch(patch: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in patch.items() if value is not None}


def _clean_optional_text(value: object, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = _clean_text(value, max_len=max_len)
    return text or None


def _clean_text(value: object, *, max_len: int) -> str:
    text = " ".join(str(value).strip().split())
    return text[:max_len]


def _memory_category(value: str) -> MemoryCategory:
    if value in {"study", "routine", "motivation", "preference", "boundary"}:
        return value  # type: ignore[return-value]
    return "preference"


def _memory_sensitivity(value: str) -> MemorySensitivity:
    if value == "sensitive":
        return "sensitive"
    return "normal"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
