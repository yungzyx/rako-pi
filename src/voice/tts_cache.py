"""TTS pre-sintetizado desde disco — el eslabón offline de la cadena de voz.

Las frases curadas (protocolo de crisis, derivaciones, fallbacks) se
sintetizan de antemano con `scripts/rako-pregen-tts` cuando hay red y
credenciales; este cliente las sirve después sin internet. Así el
protocolo de crisis nunca depende de que ElevenLabs/Google respondan.

Privacidad (CLAUDE.md §4.1.2): esto es audio GENERADO por el robot
(output). El audio del usuario nunca se persiste — este módulo no lo toca.
El índice guarda el texto curado para inspección; no contiene datos del
usuario porque solo se pre-generan frases fijas del producto.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from voice.types import AudioBuffer, SynthesisResult

_INDEX_FILENAME = "index.json"
_AUDIO_ENCODING = "MP3"
_DEFAULT_SAMPLE_RATE = 44100


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _key_for(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:24]


class PrerecordedTTS:
    """Sirve audio pre-sintetizado por hash del texto; falla si no está."""

    def __init__(self, cache_dir: Path, *, sample_rate: int = _DEFAULT_SAMPLE_RATE) -> None:
        self._cache_dir = Path(cache_dir)
        self._sample_rate = sample_rate

    def synthesize(self, text: str) -> SynthesisResult:
        cleaned = _normalize(text)
        if not cleaned:
            raise ValueError("cannot synthesize empty text")
        path = self._audio_path(cleaned)
        if not path.exists():
            raise FileNotFoundError(f"no prerecorded audio for this text (key {path.stem})")
        return SynthesisResult(
            audio=AudioBuffer(
                data=path.read_bytes(),
                sample_rate=self._sample_rate,
                encoding=_AUDIO_ENCODING,
            ),
            voice_name="prerecorded-cache",
            text_synthesized=cleaned,
        )

    def store(self, text: str, result: SynthesisResult) -> Path:
        """Guarda audio sintetizado y actualiza el índice legible."""
        cleaned = _normalize(text)
        if not cleaned:
            raise ValueError("cannot store empty text")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._audio_path(cleaned)
        path.write_bytes(result.audio.data)
        self._update_index(cleaned, path.name, result.voice_name)
        return path

    def has(self, text: str) -> bool:
        return self._audio_path(_normalize(text)).exists()

    def entry_count(self) -> int:
        if not self._cache_dir.is_dir():
            return 0
        return sum(1 for _ in self._cache_dir.glob("*.mp3"))

    def _audio_path(self, cleaned_text: str) -> Path:
        return self._cache_dir / f"{_key_for(cleaned_text)}.mp3"

    def _update_index(self, text: str, filename: str, voice_name: str) -> None:
        index_path = self._cache_dir / _INDEX_FILENAME
        index: dict[str, dict[str, str]] = {}
        if index_path.exists():
            index = json.loads(index_path.read_text(encoding="utf-8"))
        index[filename] = {"text": text, "voice": voice_name}
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
