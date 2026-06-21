from __future__ import annotations

from config import Settings
from db.database import Database
from product.support_bundle import (
    build_support_bundle,
    support_bundle_to_dict,
    write_support_bundle_json,
)


def test_support_bundle_redacts_secret_presence_and_omits_raw_values(db_conn, tmp_path) -> None:
    db = Database(db_conn)
    settings = Settings(
        _env_file=None,
        rako_device_id="rako-001",
        rako_api_token="secret-token",
        sqlite_encryption_key="x" * 64,
        openai_api_key="sk-secret",
    )

    bundle = build_support_bundle(db, settings, app_version="0.1.0")
    payload = support_bundle_to_dict(bundle)
    output = write_support_bundle_json(bundle, tmp_path / "support.json")
    text = output.read_text(encoding="utf-8")

    assert payload["device_id"] == "rako-001"
    assert payload["env_presence"]["rako_api_token"] is True
    assert "secret-token" not in str(payload)
    assert "sk-secret" not in text
    assert "No raw transcripts" in payload["notes"][0]
