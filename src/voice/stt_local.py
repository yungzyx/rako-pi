"""STT local de fallback vía whisper.cpp — el oído offline de Rako.

Cierra el gap de CLAUDE.md §4.3: sin internet, el STT cloud falla y Rako
podía hablar (frases pre-generadas) pero no entender. Con un binario de
whisper.cpp y un modelo chico (tiny/base en español), la Pi transcribe
localmente: más lento y menos preciso que el cloud, pero suficiente para
que el detector de crisis y los comandos básicos sigan funcionando.

Privacidad: el audio se escribe a un WAV temporal SOLO mientras dura la
transcripción y se elimina siempre (§4.1.2 — el audio del usuario no se
persiste).
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import wave
from pathlib import Path

from voice.types import AudioBuffer, TranscriptResult

_log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 120.0
# whisper.cpp no reporta confianza por transcript; usamos un valor fijo
# conservador para que ningún consumidor lo confunda con certeza cloud.
_LOCAL_CONFIDENCE = 0.5


class WhisperCppSTT:
    """Envuelve el binario `whisper-cli` (o `main`) de whisper.cpp."""

    def __init__(
        self,
        *,
        binary_path: str,
        model_path: str,
        language: str = "es",
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._binary_path = binary_path
        self._model_path = model_path
        self._language = language
        self._timeout_s = timeout_s

    def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
        if not audio.data:
            return TranscriptResult(text="", confidence=0.0, language=self._language)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            _write_wav(Path(tmp.name), audio)
            completed = subprocess.run(
                [
                    self._binary_path,
                    "-m",
                    self._model_path,
                    "-f",
                    tmp.name,
                    "-l",
                    self._language,
                    "-nt",  # sin timestamps
                    "-np",  # sin banner de progreso
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
                check=True,
            )
        text = " ".join(completed.stdout.split()).strip()
        return TranscriptResult(
            text=text,
            confidence=_LOCAL_CONFIDENCE if text else 0.0,
            language=self._language,
        )


class FallbackSTT:
    """Cadena de STT: cloud primario, whisper.cpp local si el cloud falla.

    Espejo de `FallbackTTS` (voice/tts.py): el fallback de bootstrap cubre
    inicialización; esta cadena cubre fallas por transcripción (sin red,
    cuota, timeout).
    """

    def __init__(self, clients: tuple) -> None:
        if not clients:
            raise ValueError("FallbackSTT requires at least one client")
        self._clients = tuple(clients)

    @property
    def clients(self) -> tuple:
        return self._clients

    def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
        last_error: Exception | None = None
        for index, client in enumerate(self._clients):
            try:
                return client.transcribe(audio)
            except Exception as exc:
                last_error = exc
                remaining = len(self._clients) - index - 1
                _log.warning(
                    "STT %s failed (%s); %d fallback(s) left",
                    type(client).__name__,
                    exc,
                    remaining,
                )
        assert last_error is not None
        raise last_error


def _write_wav(path: Path, audio: AudioBuffer) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(audio.sample_rate)
        wav.writeframes(audio.data)
