"""Tests del cliente TTS (Google Cloud Text-to-Speech)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from voice.tts import GoogleCloudTTS, TTSClient
from voice.types import AudioBuffer, SynthesisResult


@dataclass
class _FakeSynthesizeResponse:
    audio_content: bytes


@dataclass
class _RecordedCall:
    input: dict[str, Any]
    voice: dict[str, Any]
    audio_config: dict[str, Any]


class _FakeTTSClient:
    def __init__(self, audio_bytes: bytes = b"FAKEMP3DATA") -> None:
        self._audio_bytes = audio_bytes
        self.calls: list[_RecordedCall] = []

    def synthesize_speech(
        self,
        *,
        input: dict[str, Any],
        voice: dict[str, Any],
        audio_config: dict[str, Any],
    ) -> _FakeSynthesizeResponse:
        self.calls.append(
            _RecordedCall(
                input=dict(input),
                voice=dict(voice),
                audio_config=dict(audio_config),
            )
        )
        return _FakeSynthesizeResponse(audio_content=self._audio_bytes)


def test_google_cloud_tts_satisfies_protocol() -> None:
    client = GoogleCloudTTS(
        client=_FakeTTSClient(),
        voice_name="es-CL-Neural2-A",
        language_code="es-CL",
    )
    assert isinstance(client, TTSClient)


def test_synthesize_returns_audio_buffer_with_text_and_voice() -> None:
    fake = _FakeTTSClient(audio_bytes=b"AUDIO")
    client = GoogleCloudTTS(
        client=fake,
        voice_name="es-CL-Neural2-A",
        language_code="es-CL",
    )

    result = client.synthesize("Estoy contigo.")

    assert isinstance(result, SynthesisResult)
    assert isinstance(result.audio, AudioBuffer)
    assert result.audio.data == b"AUDIO"
    assert result.audio.encoding == "MP3"
    assert result.voice_name == "es-CL-Neural2-A"
    assert result.text_synthesized == "Estoy contigo."


def test_synthesize_passes_correct_request_shape() -> None:
    fake = _FakeTTSClient()
    client = GoogleCloudTTS(
        client=fake,
        voice_name="es-CL-Neural2-A",
        language_code="es-CL",
        speaking_rate=0.95,
    )

    client.synthesize("hola")

    call = fake.calls[0]
    assert call.input["text"] == "hola"
    assert call.voice["name"] == "es-CL-Neural2-A"
    assert call.voice["language_code"] == "es-CL"
    assert call.audio_config["audio_encoding"] == "MP3"
    assert call.audio_config["speaking_rate"] == 0.95


def test_synthesize_rejects_empty_text() -> None:
    fake = _FakeTTSClient()
    client = GoogleCloudTTS(
        client=fake,
        voice_name="es-CL-Neural2-A",
        language_code="es-CL",
    )

    with pytest.raises(ValueError):
        client.synthesize("   ")


def test_synthesize_with_empty_audio_response_raises() -> None:
    fake = _FakeTTSClient(audio_bytes=b"")
    client = GoogleCloudTTS(
        client=fake,
        voice_name="es-CL-Neural2-A",
        language_code="es-CL",
    )

    with pytest.raises(ValueError, match="empty"):
        client.synthesize("hola")


def test_synthesize_caps_text_length() -> None:
    # Privacidad/coste: el TTS no debe sintetizar cualquier longitud.
    fake = _FakeTTSClient()
    client = GoogleCloudTTS(
        client=fake,
        voice_name="es-CL-Neural2-A",
        language_code="es-CL",
        max_chars=100,
    )

    long_text = "x" * 500
    with pytest.raises(ValueError, match="too long"):
        client.synthesize(long_text)
