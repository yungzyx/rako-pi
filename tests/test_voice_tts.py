"""Tests del cliente TTS (Google Cloud Text-to-Speech)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from voice.tts import ElevenLabsTTS, FallbackTTS, GoogleCloudTTS, TTSClient
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
        self.closed = False

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

    def close(self) -> None:
        self.closed = True


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


def test_google_cloud_tts_closes_underlying_client() -> None:
    fake = _FakeTTSClient()
    client = GoogleCloudTTS(
        client=fake,
        voice_name="es-CL-Neural2-A",
        language_code="es-CL",
    )

    client.close()

    assert fake.closed is True


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
        self.closed = False

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

    def close(self) -> None:
        self.closed = True


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


def test_elevenlabs_tts_closes_underlying_http_client() -> None:
    fake = _FakeElevenLabsHTTPClient()
    client = ElevenLabsTTS(
        http_client=fake,
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
    )

    client.close()

    assert fake.closed is True


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


# ---------------------------------------------------------------------------
# FallbackTTS — cadena con degradación en runtime
# ---------------------------------------------------------------------------


class _StaticTTS:
    def __init__(self, voice_name: str) -> None:
        self.voice_name = voice_name
        self.calls: list[str] = []
        self.closed = False

    def synthesize(self, text: str) -> SynthesisResult:
        self.calls.append(text)
        return SynthesisResult(
            audio=AudioBuffer(data=b"AUDIO", sample_rate=44100, encoding="MP3"),
            voice_name=self.voice_name,
            text_synthesized=text,
        )

    def close(self) -> None:
        self.closed = True


class _FailingTTS:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls: list[str] = []

    def synthesize(self, text: str) -> SynthesisResult:
        self.calls.append(text)
        raise self._error


def test_fallback_tts_requires_at_least_one_client() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FallbackTTS(())


def test_fallback_tts_uses_primary_when_it_works() -> None:
    primary = _StaticTTS("primary")
    backup = _StaticTTS("backup")
    chain = FallbackTTS((primary, backup))

    result = chain.synthesize("hola")

    assert result.voice_name == "primary"
    assert backup.calls == []


def test_fallback_tts_falls_through_on_runtime_error() -> None:
    primary = _FailingTTS(RuntimeError("provider down"))
    backup = _StaticTTS("backup")
    chain = FallbackTTS((primary, backup))

    result = chain.synthesize("hola")

    assert result.voice_name == "backup"
    assert primary.calls == ["hola"]


def test_fallback_tts_raises_last_error_when_all_fail() -> None:
    first = _FailingTTS(RuntimeError("first down"))
    second = _FailingTTS(ValueError("second down"))
    chain = FallbackTTS((first, second))

    with pytest.raises(ValueError, match="second down"):
        chain.synthesize("hola")


def test_fallback_tts_close_closes_all_clients() -> None:
    primary = _StaticTTS("primary")
    backup = _StaticTTS("backup")
    chain = FallbackTTS((primary, backup))

    chain.close()

    assert primary.closed
    assert backup.closed


# ---------------------------------------------------------------------------
# Streaming — ElevenLabs /stream y delegación de la cadena
# ---------------------------------------------------------------------------


class _FakeStreamResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def __enter__(self) -> _FakeStreamResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):
        yield from self._chunks


class _FakeStreamingHTTPClient:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.stream_calls: list[str] = []

    def stream(self, method: str, url: str, **kwargs: Any) -> _FakeStreamResponse:
        self.stream_calls.append(url)
        return _FakeStreamResponse(self.chunks)


def test_elevenlabs_stream_yields_chunks_as_they_arrive() -> None:
    http = _FakeStreamingHTTPClient([b"AA", b"BB", b"CC"])
    client = ElevenLabsTTS(
        http_client=http,
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
    )

    chunks = list(client.synthesize_stream("hola rako"))

    assert chunks == [b"AA", b"BB", b"CC"]
    assert http.stream_calls == ["https://api.elevenlabs.io/v1/text-to-speech/voice-123/stream"]


def test_elevenlabs_stream_rejects_empty_text() -> None:
    client = ElevenLabsTTS(
        http_client=_FakeStreamingHTTPClient([]),
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
    )

    with pytest.raises(ValueError):
        list(client.synthesize_stream("  "))


def test_fallback_chain_exposes_first_streaming_client() -> None:
    plain = _StaticTTS("plain")
    streaming = ElevenLabsTTS(
        http_client=_FakeStreamingHTTPClient([b"X"]),
        api_key="el-test",
        voice_id="voice-123",
        model="eleven_flash_v2_5",
    )
    chain = FallbackTTS((plain, streaming))

    assert chain.stream_client() is streaming


def test_fallback_chain_without_streaming_clients_returns_none() -> None:
    chain = FallbackTTS((_StaticTTS("a"), _StaticTTS("b")))

    assert chain.stream_client() is None
