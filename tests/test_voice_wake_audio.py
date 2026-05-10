from __future__ import annotations

from pathlib import Path

import pytest

from voice.wake_audio import PorcupineWakeWordConfig, _pcm16_bytes_to_ints


def test_pcm16_bytes_to_ints_decodes_little_endian_signed() -> None:
    data = b"\x00\x00\xff\x7f\x00\x80\xff\xff"

    assert _pcm16_bytes_to_ints(data) == [0, 32767, -32768, -1]


def test_pcm16_bytes_to_ints_rejects_odd_length() -> None:
    with pytest.raises(ValueError):
        _pcm16_bytes_to_ints(b"\x00")


def test_porcupine_config_validates_keyword_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        PorcupineWakeWordConfig(access_key="key", keyword_path=str(tmp_path / "missing.ppn"))


def test_porcupine_config_validates_sensitivity(tmp_path: Path) -> None:
    keyword = tmp_path / "oye-rako.ppn"
    keyword.write_bytes(b"dummy")

    with pytest.raises(ValueError):
        PorcupineWakeWordConfig(
            access_key="key",
            keyword_path=str(keyword),
            sensitivity=1.5,
        )
