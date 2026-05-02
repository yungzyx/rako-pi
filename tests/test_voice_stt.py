"""Tests del cliente STT (Google Cloud Speech)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from voice.stt import GoogleCloudSTT, STTClient
from voice.types import AudioBuffer, TranscriptResult


@dataclass
class _FakeAlternative:
    transcript: str
    confidence: float = 0.92


@dataclass
class _FakeResult:
    alternatives: list[_FakeAlternative]


@dataclass
class _FakeResponse:
    results: list[_FakeResult]


@dataclass
class _RecordedCall:
    config: dict[str, Any]
    audio: dict[str, Any]


class _FakeSpeechClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[_RecordedCall] = []

    def recognize(self, *, config: dict[str, Any], audio: dict[str, Any]) -> _FakeResponse:
        self.calls.append(_RecordedCall(config=dict(config), audio=dict(audio)))
        return self._response


def _audio() -> AudioBuffer:
    return AudioBuffer(data=b"\x00" * 32000, sample_rate=16000, encoding="LINEAR16")


def _response_with(transcript: str, confidence: float = 0.92) -> _FakeResponse:
    return _FakeResponse(
        results=[
            _FakeResult(
                alternatives=[_FakeAlternative(transcript=transcript, confidence=confidence)]
            )
        ]
    )


def test_google_cloud_stt_satisfies_protocol() -> None:
    client = GoogleCloudSTT(client=_FakeSpeechClient(_response_with("x")), language="es-CL")
    assert isinstance(client, STTClient)


def test_transcribe_returns_top_alternative_text() -> None:
    fake = _FakeSpeechClient(_response_with("hola rako", confidence=0.91))
    client = GoogleCloudSTT(client=fake, language="es-CL")

    result = client.transcribe(_audio())

    assert isinstance(result, TranscriptResult)
    assert result.text == "hola rako"
    assert result.confidence == pytest.approx(0.91)
    assert result.language == "es-CL"


def test_transcribe_passes_encoding_and_sample_rate() -> None:
    fake = _FakeSpeechClient(_response_with("x"))
    client = GoogleCloudSTT(client=fake, language="es-CL")

    client.transcribe(_audio())

    call = fake.calls[0]
    assert call.config["encoding"] == "LINEAR16"
    assert call.config["sample_rate_hertz"] == 16000
    assert call.config["language_code"] == "es-CL"
    assert call.audio["content"] == b"\x00" * 32000


def test_transcribe_rejects_empty_audio() -> None:
    fake = _FakeSpeechClient(_response_with("x"))
    client = GoogleCloudSTT(client=fake, language="es-CL")

    empty = AudioBuffer(data=b"", sample_rate=16000, encoding="LINEAR16")
    with pytest.raises(ValueError):
        client.transcribe(empty)


def test_transcribe_with_no_results_raises() -> None:
    fake = _FakeSpeechClient(_FakeResponse(results=[]))
    client = GoogleCloudSTT(client=fake, language="es-CL")

    with pytest.raises(ValueError, match="no transcription"):
        client.transcribe(_audio())


def test_transcribe_with_empty_alternatives_raises() -> None:
    fake = _FakeSpeechClient(_FakeResponse(results=[_FakeResult(alternatives=[])]))
    client = GoogleCloudSTT(client=fake, language="es-CL")

    with pytest.raises(ValueError):
        client.transcribe(_audio())


def test_transcribe_clamps_confidence_to_unit_interval() -> None:
    # Si Google llegara a devolver algo fuera de rango, normalizamos.
    fake = _FakeSpeechClient(_response_with("x", confidence=1.5))
    client = GoogleCloudSTT(client=fake, language="es-CL")

    result = client.transcribe(_audio())

    assert 0.0 <= result.confidence <= 1.0


def test_transcribe_picks_first_result_when_multiple() -> None:
    fake = _FakeSpeechClient(
        _FakeResponse(
            results=[
                _FakeResult(alternatives=[_FakeAlternative(transcript="primero", confidence=0.9)]),
                _FakeResult(alternatives=[_FakeAlternative(transcript="segundo", confidence=0.8)]),
            ]
        )
    )
    client = GoogleCloudSTT(client=fake, language="es-CL")

    result = client.transcribe(_audio())

    assert result.text == "primero"
