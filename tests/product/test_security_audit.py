from __future__ import annotations

from config import Settings
from product.security_audit import build_security_audit, security_audit_to_dict


def test_security_audit_fails_prod_without_api_token() -> None:
    audit = build_security_audit(Settings(_env_file=None, rako_env="prod"))

    payload = security_audit_to_dict(audit)

    assert payload["ready_for_prod"] is False
    assert any(
        check["name"] == "api token" and check["status"] == "fail" for check in payload["checks"]
    )


def test_security_audit_fails_prod_without_sqlite_encryption_key() -> None:
    # CLAUDE.md §4.1.6: producción no debe correr sin SQLCipher activo.
    audit = build_security_audit(
        Settings(_env_file=None, rako_env="prod", rako_api_token="local-token")
    )

    assert audit.ready_for_prod is False
    assert any(
        check.name == "sqlite encryption" and check.status == "fail" for check in audit.checks
    )


def test_security_audit_warns_dev_without_sqlite_encryption_key() -> None:
    # En dev (mac, sin libsqlcipher) es esperado no tener key — no debe
    # bloquear `ready_for_prod` con un fail espurio.
    audit = build_security_audit(Settings(_env_file=None, rako_env="dev"))

    assert any(
        check.name == "sqlite encryption" and check.status == "warn" for check in audit.checks
    )


def test_security_audit_requires_whatsapp_secret_for_cloud() -> None:
    audit = build_security_audit(
        Settings(
            _env_file=None,
            rako_env="prod",
            rako_api_token="local-token",
            whatsapp_client="cloud",
        )
    )

    assert audit.ready_for_prod is False
    assert any(
        check.name == "whatsapp webhook secret" and check.status == "fail" for check in audit.checks
    )
