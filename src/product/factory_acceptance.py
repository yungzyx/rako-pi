"""Factory acceptance checklist for shipping a Rako device.

The checklist mixes automatic software checks with explicit manual gates for
hardware and user experience. A board is ready to ship only when automatic
checks pass and a human has completed the manual hardware/UX checklist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from config import Settings
from db.database import Database
from product.user_config import UserConfigService

AcceptanceStatus = Literal["ok", "warn", "fail", "manual"]


@dataclass(frozen=True, slots=True)
class AcceptanceItem:
    category: str
    name: str
    status: AcceptanceStatus
    detail: str


@dataclass(frozen=True, slots=True)
class AcceptanceChecklist:
    ready_for_handoff: bool
    automatic_failures: int
    automatic_warnings: int
    manual_items: int
    items: tuple[AcceptanceItem, ...]


def build_factory_acceptance_checklist(
    db: Database,
    settings: Settings,
) -> AcceptanceChecklist:
    config = UserConfigService(db)
    status = config.onboarding_status()
    consent = config.get_consent()
    channels = config.get_channels()
    items: list[AcceptanceItem] = []

    items.append(
        _item(
            "onboarding",
            "user profile",
            "ok" if status.profile.preferred_name else "fail",
            status.profile.preferred_name or "missing preferred_name",
        )
    )
    items.append(
        _item(
            "onboarding",
            "wifi ssid",
            "ok" if channels.wifi_ssid else "fail",
            channels.wifi_ssid or "missing wifi_ssid",
        )
    )
    items.append(
        _item(
            "privacy",
            "privacy consent",
            "ok" if db.config.get("product.privacy_consent") else "fail",
            "recorded" if db.config.get("product.privacy_consent") else "missing consent record",
        )
    )
    items.append(
        _item(
            "whatsapp",
            "whatsapp outbound",
            "ok" if config.whatsapp_can_send() else "warn",
            "enabled" if config.whatsapp_can_send() else "disabled or missing number",
        )
    )
    items.append(
        _item(
            "whatsapp",
            "proactive coaching",
            "ok" if config.proactive_messages_can_send() else "warn",
            "enabled" if config.proactive_messages_can_send() else "disabled",
        )
    )
    items.append(
        _item(
            "wellbeing",
            "wellbeing escalation",
            "ok"
            if (not consent.wellbeing_escalation_enabled or channels.wellbeing_unit_phone)
            else "fail",
            "configured"
            if channels.wellbeing_unit_phone
            else "not enabled"
            if not consent.wellbeing_escalation_enabled
            else "missing phone",
        )
    )
    items.append(
        _item(
            "secrets",
            "sqlite encryption key",
            "ok" if settings.sqlite_encryption_key else "warn",
            "configured" if settings.sqlite_encryption_key else "missing SQLITE_ENCRYPTION_KEY",
        )
    )
    items.append(
        _item(
            "secrets",
            "api token",
            "ok" if settings.rako_env == "dev" or settings.rako_api_token else "fail",
            "configured" if settings.rako_api_token else f"{settings.rako_env} without token",
        )
    )
    items.append(
        _item(
            "voice",
            "stt credentials",
            "ok" if _stt_configured(settings) else "fail",
            settings.stt_provider,
        )
    )
    items.append(
        _item(
            "voice",
            "tts credentials",
            "ok" if _tts_configured(settings) else "fail",
            settings.tts_provider,
        )
    )

    items.extend(_manual_items())

    automatic = [item for item in items if item.status != "manual"]
    failures = sum(1 for item in automatic if item.status == "fail")
    warnings = sum(1 for item in automatic if item.status == "warn")
    manual = sum(1 for item in items if item.status == "manual")
    return AcceptanceChecklist(
        ready_for_handoff=failures == 0,
        automatic_failures=failures,
        automatic_warnings=warnings,
        manual_items=manual,
        items=tuple(items),
    )


def acceptance_checklist_to_dict(checklist: AcceptanceChecklist) -> dict[str, object]:
    return {
        "ready_for_handoff": checklist.ready_for_handoff,
        "automatic_failures": checklist.automatic_failures,
        "automatic_warnings": checklist.automatic_warnings,
        "manual_items": checklist.manual_items,
        "items": [asdict(item) for item in checklist.items],
    }


def _manual_items() -> tuple[AcceptanceItem, ...]:
    return (
        _item(
            "hardware",
            "microphone capture quality",
            "manual",
            "run rako-doctor --record; target clear speech without clipping",
        ),
        _item(
            "hardware",
            "speaker playback",
            "manual",
            "run rako-doctor --sound and confirm voice/cues are audible",
        ),
        _item(
            "hardware",
            "oled eyes",
            "manual",
            "run rako-doctor --oled and confirm warm visible expressions",
        ),
        _item(
            "hardware",
            "button interaction",
            "manual",
            "press ReSpeaker button and confirm listening starts quickly",
        ),
        _item(
            "academic",
            "focus flow",
            "manual",
            "say 'estudiar calculo 25 minutos' and confirm timer/response",
        ),
        _item(
            "safety",
            "crisis bypass",
            "manual",
            "run demo crisis phrase and confirm curated response, no LLM improvisation",
        ),
    )


def _stt_configured(settings: Settings) -> bool:
    if settings.stt_provider == "openai_whisper":
        return bool(settings.openai_api_key)
    if settings.stt_provider == "google":
        return bool(settings.google_application_credentials)
    return False


def _tts_configured(settings: Settings) -> bool:
    if settings.tts_provider == "elevenlabs":
        return bool(settings.elevenlabs_api_key)
    if settings.tts_provider == "google":
        return bool(settings.google_application_credentials)
    return False


def _item(
    category: str,
    name: str,
    status: AcceptanceStatus,
    detail: str,
) -> AcceptanceItem:
    return AcceptanceItem(category=category, name=name, status=status, detail=detail)
