from __future__ import annotations

from product.update_status import build_update_status, current_app_version, update_status_to_dict


def test_update_status_is_read_only_and_reports_channel(monkeypatch) -> None:
    monkeypatch.setenv("RAKO_RELEASE_CHANNEL", "beta")
    monkeypatch.setenv("RAKO_BUILD_SHA", "abc123")

    status = build_update_status()
    payload = update_status_to_dict(status)

    assert payload["app_version"] == current_app_version()
    assert payload["build_sha"] == "abc123"
    assert payload["release_channel"] == "beta"
    assert payload["update_apply_enabled"] is False
    assert payload["update_available"] is False


def test_update_status_defaults_unknown_channel_to_stable(monkeypatch) -> None:
    monkeypatch.setenv("RAKO_RELEASE_CHANNEL", "nightly")
    monkeypatch.delenv("RAKO_BUILD_SHA", raising=False)

    status = build_update_status()

    assert status.release_channel == "stable"
