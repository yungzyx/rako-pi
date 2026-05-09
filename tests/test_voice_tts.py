"""Tests del cliente TTS (Google Cloud Text-to-Speech)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from voice.tts import ElevenLabsTTS, GoogleCloudTTS, TTSClient
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


class _FakeElevenLabsHTTPResponse:
    def __init__(self, *, content: bytes = b"ELEVENMP3") -> None:
        self.content = content
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True


class _FakeElevenLabsHTTPClient:
    def __init__(self, response: _FakeElevenLabsHTTPResponse | None = None) -> None:
        self.response = response or _FakeElevenLabsHTTPResponse()
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> _FakeElevenLabsHTTPResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return self.response


def test_elevenlabs_tts_satisfies_protocol() -> None:
    client = ElevenLabsTTS(
        http_client=_FakeElevenLabsHTTPClient(),
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
    )

    assert isinstance(client, TTSClient)


def test_elevenlabs_tts_posts_expected_request_shape() -> None:
    fake = _FakeElevenLabsHTTPClient()
    client = ElevenLabsTTS(
        http_client=fake,
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
        stability=0.55,
        similarity_boost=0.8,
    )

    result = client.synthesize(" Estoy contigo. ")

    call = fake.calls[0]
    assert call["url"].endswith("/v1/text-to-speech/voice-123")
    assert call["headers"]["xi-api-key"] == "el-test"
    assert call["headers"]["accept"] == "audio/mpeg"
    assert call["json"]["text"] == "Estoy contigo."
    assert call["json"]["model_id"] == "eleven_flash_v2_5"
    assert call["json"]["voice_settings"]["stability"] == 0.55
    assert call["json"]["voice_settings"]["similarity_boost"] == 0.8
    assert result.audio.data == b"ELEVENMP3"
    assert result.audio.encoding == "MP3"
    assert result.voice_name == "elevenlabs:voice-123"
    assert result.text_synthesized == "Estoy contigo."


def test_elevenlabs_tts_rejects_empty_text() -> None:
    client = ElevenLabsTTS(
        http_client=_FakeElevenLabsHTTPClient(),
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
    )

    with pytest.raises(ValueError):
        client.synthesize(" ")


def test_elevenlabs_tts_rejects_empty_audio_response() -> None:
    fake = _FakeElevenLabsHTTPClient(_FakeElevenLabsHTTPResponse(content=b""))
    client = ElevenLabsTTS(
        http_client=fake,
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
    )

    with pytest.raises(ValueError, match="empty"):
        client.synthesize("hola")


def test_elevenlabs_tts_caps_text_length() -> None:
    client = ElevenLabsTTS(
        http_client=_FakeElevenLabsHTTPClient(),
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
        max_chars=100,
    )

    with pytest.raises(ValueError, match="too long"):
        client.synthesize("x" * 500)
