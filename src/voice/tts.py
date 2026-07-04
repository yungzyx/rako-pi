"""Clientes Text-to-Speech.

`GoogleCloudTTS` envuelve `google.cloud.texttospeech_v1.TextToSpeechClient`.
Por defecto usa una voz neuronal en español chileno y MP3 como salida.
`ElevenLabsTTS` es el proveedor principal recomendado para la voz cálida
del robot; Google queda como fallback estable.
`FallbackTTS` encadena clientes en runtime: si el primario falla en una
síntesis concreta (red, cuota, proveedor caído), prueba el siguiente en vez
de dejar al robot mudo.
`max_chars` evita gastar cuotas en textos accidentalmente enormes.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Final, Protocol, runtime_checkable

from voice.types import AudioBuffer, SynthesisResult

_log = logging.getLogger(__name__)

_DEFAULT_MAX_CHARS: Final[int] = 800


@runtime_checkable
class TTSClient(Protocol):
    def synthesize(self, text: str) -> SynthesisResult: ...


class GoogleCloudTTS:
    def __init__(
        self,
        client: Any,
        *,
        voice_name: str,
        language_code: str,
        speaking_rate: float = 0.95,
        max_chars: int = _DEFAULT_MAX_CHARS,
        sample_rate: int = 22050,
    ) -> None:
        self._client = client
        self._voice_name = voice_name
        self._language_code = language_code
        self._speaking_rate = speaking_rate
        self._max_chars = max_chars
        self._sample_rate = sample_rate

    def synthesize(self, text: str) -> SynthesisResult:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("cannot synthesize empty text")
        if len(cleaned) > self._max_chars:
            raise ValueError(f"text too long: {len(cleaned)} chars (max {self._max_chars})")

        response = self._client.synthesize_speech(
            input={"text": cleaned},
            voice={
                "name": self._voice_name,
                "language_code": self._language_code,
            },
            audio_config={
                "audio_encoding": "MP3",
                "speaking_rate": self._speaking_rate,
            },
        )

        if not response.audio_content:
            raise ValueError("TTS returned empty audio content")

        audio = AudioBuffer(
            data=response.audio_content,
            sample_rate=self._sample_rate,
            encoding="MP3",
        )
        return SynthesisResult(
            audio=audio,
            voice_name=self._voice_name,
            text_synthesized=cleaned,
        )

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


class ElevenLabsTTS:
    def __init__(
        self,
        http_client: Any,
        *,
        api_key: str,
        voice_id: str,
        model: str,
        stability: float = 0.55,
        similarity_boost: float = 0.8,
        timeout_s: float = 15.0,
        max_chars: int = _DEFAULT_MAX_CHARS,
        sample_rate: int = 44100,
    ) -> None:
        self._http = http_client
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._timeout_s = timeout_s
        self._max_chars = max_chars
        self._sample_rate = sample_rate

    def synthesize(self, text: str) -> SynthesisResult:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("cannot synthesize empty text")
        if len(cleaned) > self._max_chars:
            raise ValueError(f"text too long: {len(cleaned)} chars (max {self._max_chars})")

        response = self._http.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}",
            headers={
                "accept": "audio/mpeg",
                "content-type": "application/json",
                "xi-api-key": self._api_key,
            },
            json={
                "text": cleaned,
                "model_id": self._model,
                "voice_settings": {
                    "stability": self._stability,
                    "similarity_boost": self._similarity_boost,
                },
            },
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        if not response.content:
            raise ValueError("TTS returned empty audio content")

        audio = AudioBuffer(
            data=response.content,
            sample_rate=self._sample_rate,
            encoding="MP3",
        )
        return SynthesisResult(
            audio=audio,
            voice_name=f"elevenlabs:{self._voice_id}",
            text_synthesized=cleaned,
        )

    def synthesize_stream(self, text: str):
        """Genera chunks de MP3 a medida que llegan del endpoint /stream.

        Permite empezar la reproducción con los primeros bytes en vez de
        esperar la síntesis completa. El caller debe consumir el iterador
        entero (o cerrar el stream) para liberar la conexión.
        """
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("cannot synthesize empty text")
        if len(cleaned) > self._max_chars:
            raise ValueError(f"text too long: {len(cleaned)} chars (max {self._max_chars})")
        with self._http.stream(
            "POST",
            f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}/stream",
            headers={
                "accept": "audio/mpeg",
                "content-type": "application/json",
                "xi-api-key": self._api_key,
            },
            json={
                "text": cleaned,
                "model_id": self._model,
                "voice_settings": {
                    "stability": self._stability,
                    "similarity_boost": self._similarity_boost,
                },
            },
            timeout=self._timeout_s,
        ) as response:
            response.raise_for_status()
            yield from response.iter_bytes()

    def close(self) -> None:
        close = getattr(self._http, "close", None)
        if callable(close):
            close()


class FallbackTTS:
    """Cadena de TTS con degradación en runtime.

    El fallback de bootstrap solo cubre fallas de *inicialización*; esta
    cadena cubre fallas por síntesis (timeout, cuota agotada, proveedor
    caído). Se intenta cada cliente en orden y solo se levanta el último
    error si ninguno pudo sintetizar.
    """

    def __init__(self, clients: Sequence[TTSClient]) -> None:
        if not clients:
            raise ValueError("FallbackTTS requires at least one client")
        self._clients = tuple(clients)

    @property
    def clients(self) -> tuple[TTSClient, ...]:
        return self._clients

    def synthesize(self, text: str) -> SynthesisResult:
        last_error: Exception | None = None
        for index, client in enumerate(self._clients):
            try:
                return client.synthesize(text)
            except Exception as exc:
                last_error = exc
                remaining = len(self._clients) - index - 1
                _log.warning(
                    "TTS %s failed (%s); %d fallback(s) left",
                    type(client).__name__,
                    exc,
                    remaining,
                )
        assert last_error is not None  # len(clients) >= 1 garantiza un intento
        raise last_error

    def stream_client(self) -> TTSClient | None:
        """Primer cliente de la cadena que soporta streaming, si hay."""
        for client in self._clients:
            if callable(getattr(client, "synthesize_stream", None)):
                return client
        return None

    def close(self) -> None:
        for client in self._clients:
            close = getattr(client, "close", None)
            if callable(close):
                close()
