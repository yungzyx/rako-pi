from __future__ import annotations

import json

from scripts.rako_first_run import main


def test_rako_first_run_cli_prints_json(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-test-001")
    monkeypatch.setenv("SQLITE_ENCRYPTION_KEY", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setenv("STT_PROVIDER", "openai_whisper")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")

    code = main(
        [
            "--name",
            "Nico",
            "--wifi-ssid",
            "Casa",
            "--enable-whatsapp",
            "--whatsapp-number",
            "+56912345678",
            "--memory",
            "Prefiere bloques cortos",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ready"] is True
    assert payload["memories_added"] == 1
    assert payload["onboarding"]["profile"]["preferred_name"] == "Nico"
