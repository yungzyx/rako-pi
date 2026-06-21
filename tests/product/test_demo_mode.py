from __future__ import annotations

from product.demo_mode import build_demo_mode, demo_mode_to_dict


def test_demo_mode_lists_safe_commands_and_notes() -> None:
    payload = demo_mode_to_dict(build_demo_mode())

    assert payload["ready"] is True
    assert any("rako-first-run" in command for command in payload["commands"])
    assert any("No usar números reales" in note for note in payload["safety_notes"])
