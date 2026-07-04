"""Production security checks for a local Rako device."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from config import Settings

SecurityStatus = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class SecurityCheck:
    name: str
    status: SecurityStatus
    detail: str


@dataclass(frozen=True, slots=True)
class SecurityAudit:
    ready_for_prod: bool
    failures: int
    warnings: int
    checks: tuple[SecurityCheck, ...]


def build_security_audit(settings: Settings) -> SecurityAudit:
    checks = (
        _check(
            "api token",
            "ok" if settings.rako_env == "dev" or settings.rako_api_token else "fail",
            "configured" if settings.rako_api_token else f"{settings.rako_env} without token",
        ),
        _check(
            "sqlite encryption",
            "ok"
            if settings.sqlite_encryption_key
            else ("warn" if settings.rako_env == "dev" else "fail"),
            "configured" if settings.sqlite_encryption_key else "missing SQLITE_ENCRYPTION_KEY",
        ),
        _check(
            "local API exposure",
            "warn" if settings.rako_env == "dev" else "ok",
            "dev permits tokenless local API" if settings.rako_env == "dev" else settings.rako_env,
        ),
        _check(
            "whatsapp webhook secret",
            "ok"
            if settings.whatsapp_client != "cloud" or settings.whatsapp_cloud_app_secret
            else "fail",
            "configured" if settings.whatsapp_cloud_app_secret else settings.whatsapp_client,
        ),
        _check(
            "ota apply gate",
            "ok" if not settings.rako_update_apply_enabled else "warn",
            "manual apply disabled"
            if not settings.rako_update_apply_enabled
            else "automatic apply enabled; require signed releases and rollback",
        ),
        _check(
            "hotspot gate",
            "ok" if not settings.rako_setup_hotspot_enabled or settings.rako_api_token else "fail",
            "hotspot disabled or token configured",
        ),
    )
    failures = sum(1 for check in checks if check.status == "fail")
    warnings = sum(1 for check in checks if check.status == "warn")
    return SecurityAudit(
        ready_for_prod=failures == 0,
        failures=failures,
        warnings=warnings,
        checks=checks,
    )


def security_audit_to_dict(audit: SecurityAudit) -> dict[str, Any]:
    return {
        "ready_for_prod": audit.ready_for_prod,
        "failures": audit.failures,
        "warnings": audit.warnings,
        "checks": [asdict(check) for check in audit.checks],
    }


def _check(name: str, status: SecurityStatus, detail: str) -> SecurityCheck:
    return SecurityCheck(name=name, status=status, detail=detail)
