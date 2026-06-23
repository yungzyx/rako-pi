from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_doctor_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "rako_doctor.py"
    spec = importlib.util.spec_from_file_location("rako_doctor_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_boot_audio_overlay_passes_when_seeed_overlay_and_i2s_are_enabled(
    tmp_path: Path,
) -> None:
    doctor = _load_doctor_module()
    config = tmp_path / "config.txt"
    config.write_text(
        "\n".join(
            (
                "dtparam=i2c_arm=on",
                "dtoverlay=i2s-mmap",
                "dtparam=i2s=on",
                "dtoverlay=seeed-2mic-voicecard",
            )
        ),
        encoding="utf-8",
    )

    result = doctor._check_boot_audio_overlay((config,))

    assert result.status == "ok"
    assert str(config) in result.detail


def test_boot_audio_overlay_fails_with_actionable_fix_when_missing(
    tmp_path: Path,
) -> None:
    doctor = _load_doctor_module()
    config = tmp_path / "config.txt"
    config.write_text("dtparam=i2c_arm=on\n", encoding="utf-8")

    result = doctor._check_boot_audio_overlay((config,))

    assert result.status == "fail"
    assert "dtoverlay=seeed-2mic-voicecard" in result.detail
    assert "sudo ./scripts/rako-fix-audio-boot" in result.detail
