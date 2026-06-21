from __future__ import annotations

from scripts.rako_support_bundle import main


def test_rako_support_bundle_writes_json(monkeypatch, tmp_path, capsys) -> None:
    output = tmp_path / "bundle.json"
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "rako.db"))
    monkeypatch.setenv("RAKO_DEVICE_ID", "rako-001")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")

    code = main(["--output", str(output)])
    text = output.read_text(encoding="utf-8")

    assert code == 0
    assert "Wrote sanitized support bundle" in capsys.readouterr().out
    assert "rako-001" in text
    assert "sk-secret" not in text
