from __future__ import annotations

import json

from config import Settings
from product.update_status import (
    artifact_sha256,
    build_update_plan,
    build_update_status,
    current_app_version,
    parse_update_manifest,
    update_status_to_dict,
)


def test_update_status_is_read_only_and_reports_channel(monkeypatch) -> None:
    settings = Settings(_env_file=None, rako_release_channel="beta")

    status = build_update_status(settings)
    payload = update_status_to_dict(status)

    assert payload["app_version"] == current_app_version()
    assert payload["release_channel"] == "beta"
    assert payload["update_apply_enabled"] is False
    assert payload["update_available"] is False


def test_update_plan_is_not_configured_without_manifest() -> None:
    settings = Settings(_env_file=None)

    plan = build_update_plan(settings)

    assert plan.decision == "not_configured"
    assert plan.target_version is None
    assert plan.steps == ()


def test_update_plan_detects_available_manifest(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "channel": "stable",
                "artifact_url": "https://example.com/rako-0.2.0.tar.gz",
                "artifact_sha256": "a" * 64,
                "rollback_version": "0.1.0",
                "minimum_version": "0.1.0",
                "release_notes": "Mejoras OTA",
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        rako_release_channel="stable",
        rako_update_manifest_path=str(manifest_path),
    )

    status = build_update_status(settings)
    plan = build_update_plan(settings)

    assert status.update_available is True
    assert status.source == "manifest"
    assert plan.decision == "available"
    assert plan.target_version == "0.2.0"
    assert "Verify artifact SHA-256 before unpacking." in plan.steps
    assert plan.manifest is not None
    assert plan.manifest.rollback_version == "0.1.0"


def test_update_plan_blocks_wrong_channel(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "channel": "beta",
                "artifact_url": "https://example.com/rako-0.2.0.tar.gz",
                "artifact_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        rako_release_channel="stable",
        rako_update_manifest_path=str(manifest_path),
    )

    plan = build_update_plan(settings)

    assert plan.decision == "blocked"
    assert "does not match" in plan.reasons[0]


def test_parse_update_manifest_rejects_bad_hash() -> None:
    manifest = parse_update_manifest(
        {
            "version": "0.2.0",
            "channel": "stable",
            "artifact_url": "https://example.com/rako.tar.gz",
            "artifact_sha256": "bad",
        }
    )

    assert manifest is None


def test_artifact_sha256(tmp_path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("rako", encoding="utf-8")

    digest = artifact_sha256(artifact)

    assert digest == "a9823fe541607cf561158375077a75630f5b7f0ca839cdc830b1cef182a2b03d"
