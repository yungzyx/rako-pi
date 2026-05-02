"""Tests del sanitizador de payloads — el last-line-of-defense contra leaks."""

from __future__ import annotations

from sync.sanitizer import sanitize_payload


def test_drops_pii_keys() -> None:
    payload = {
        "task_count": 3,
        "name": "Yung",
        "email": "y@example.com",
        "phone": "+56...",
        "address": "Calle X 123",
    }

    out = sanitize_payload(payload)

    assert "task_count" in out
    assert "name" not in out
    assert "email" not in out
    assert "phone" not in out
    assert "address" not in out


def test_drops_emotional_keys() -> None:
    payload = {
        "valence": -0.5,
        "arousal": 0.8,
        "dominance": 0.4,
        "level": 3,
    }

    out = sanitize_payload(payload)

    assert "valence" not in out
    assert "arousal" not in out
    assert "dominance" not in out
    assert out["level"] == 3


def test_drops_transcript_and_audio_keys() -> None:
    payload = {
        "transcript": "no quiero seguir",
        "transcription_excerpt": "...",
        "audio_path": "/tmp/x.wav",
        "ok": True,
    }

    out = sanitize_payload(payload)

    assert "transcript" not in out
    assert "transcription_excerpt" not in out
    assert "audio_path" not in out
    assert out["ok"] is True


def test_drops_non_primitive_values() -> None:
    payload = {
        "task_count": 3,
        "nested": {"secret": "x"},
        "items": [1, 2, 3],
        "obj": object(),
    }

    out = sanitize_payload(payload)

    assert out == {"task_count": 3}


def test_caps_string_length() -> None:
    payload = {"note": "x" * 5000}

    out = sanitize_payload(payload)

    assert len(out["note"]) <= 500


def test_keeps_primitives() -> None:
    payload = {"i": 1, "f": 1.5, "b": True, "s": "ok", "n": None}

    out = sanitize_payload(payload)

    assert out == {"i": 1, "f": 1.5, "b": True, "s": "ok", "n": None}


def test_case_insensitive_key_matching() -> None:
    payload = {"Email": "x", "TRANSCRIPT": "y", "Valence": 0.5, "ok": 1}

    out = sanitize_payload(payload)

    assert out == {"ok": 1}
