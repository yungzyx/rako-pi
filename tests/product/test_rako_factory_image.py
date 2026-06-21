from __future__ import annotations

from scripts.rako_factory_image import main


def test_rako_factory_image_writes_env_and_card(tmp_path, capsys) -> None:
    env_path = tmp_path / "unit.env"
    card_path = tmp_path / "card.svg"

    code = main(
        [
            "--serial",
            "SN-001",
            "--lot",
            "pilot-a",
            "--write-env",
            str(env_path),
            "--write-card-svg",
            str(card_path),
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "rako-SN-001" in output
    assert "RAKO_API_TOKEN=" in env_path.read_text(encoding="utf-8")
    assert "Rako Setup" in card_path.read_text(encoding="utf-8")
