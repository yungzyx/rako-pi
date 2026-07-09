"""Bootstrap del cerebro — arma el grafo de dependencias.

`build_dev_application(settings)` compone una `Application` con fakes para CI,
demos y desarrollo sin hardware. `build_pi_application(settings)` intenta usar
las implementaciones reales disponibles en la Raspberry Pi y cae a fakes cuando
faltan drivers o credenciales.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from channels.whatsapp.client import (
    InMemoryWhatsAppClient,
    WhatsAppClient,
    WhatsAppCloudClient,
)
from channels.whatsapp.crisis_notifier import WhatsAppCrisisNotifier
from config import Settings
from db.database import Database
from hardware.audio import InMemoryCapture, InMemoryPlayback
from hardware.event_bus import HardwareEventBus, InMemoryHardwareEventBus
from hardware.leds import (
    CrisisLightingAdapter,
    FakeLEDController,
    LEDController,
)
from hardware.servos import FakeServoController, ServoController
from orchestrator.llm_client import (
    AnthropicLLMClient,
    LLMClient,
    LLMResponse,
    OpenAILLMClient,
)
from orchestrator.orchestrator import Orchestrator
from orchestrator.prompts import extract_system_prompt
from rag.chroma_retriever import ChromaRetriever
from rag.client import InMemoryRetriever, Retriever
from rag.embeddings import build_embedder
from safety.protocol import CrisisProtocol
from safety.types import CrisisSignal
from sync.coordinator import SyncCoordinator
from sync.firebase_client import FakeFirebaseClient, FirebaseClient
from sync.queue import SyncQueue
from voice.audio_io import AudioCaptureSource, AudioPlaybackSink
from voice.stt import GoogleCloudSTT, STTClient
from voice.stt_local import FallbackSTT, WhisperCppSTT
from voice.stt_openai import OpenAIWhisperSTT
from voice.tts import ElevenLabsTTS, FallbackTTS, GoogleCloudTTS, TTSClient
from voice.tts_cache import PrerecordedTTS
from voice.types import AudioBuffer, SynthesisResult, TranscriptResult
from voice.wake_word import SubstringWakeWordDetector, WakeWordDetector

_log = logging.getLogger(__name__)

_FALLBACK_SYSTEM_PROMPT = (
    "Eres Rako: un asistente académico para estudiantes universitarios. "
    "Tono adulto, directo, cálido y natural, sin frases de plantilla. "
    "Responde corto (2-4 oraciones), con una sola acción concreta. "
    "No repitas el contexto agregado como 'no tienes tareas pendientes' salvo que el usuario pregunte. "
    "Si el usuario inicia un conteo, pomodoro o foco, interpreta la actividad real y evita títulos incompletos."
)


# ---------------------------------------------------------------------------
# Fakes para colaboradores que en producción salen del sistema
# ---------------------------------------------------------------------------


@dataclass
class _LoggingVoicePlayer:
    log: list[str] = field(default_factory=list)

    def play_prerecorded(self, response_id: str) -> None:
        self.log.append(f"play_prerecorded({response_id})")


@dataclass
class _LoggingNotifier:
    notified: list[CrisisSignal] = field(default_factory=list)
    resources_shown: int = 0

    def notify_trusted_contact(self, signal: CrisisSignal) -> None:
        self.notified.append(signal)

    def show_resources(self) -> None:
        self.resources_shown += 1


@dataclass
class _CannedLLMClient:
    """LLM fake — devuelve una respuesta canned, pensada para CI/demo offline."""

    canned_text: str = (
        "Estoy aquí. Si quieres, prueba algo pequeño: respira lento durante "
        "30 segundos. Yo me quedo contigo."
    )

    def generate(
        self,
        query: str,
        chunks: tuple,
        context: Any,
    ) -> LLMResponse:
        return LLMResponse(
            text=self.canned_text,
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )


@dataclass
class _CannedSTT:
    """STT fake — devuelve un placeholder seguro para que el loop
    progrese end-to-end en dev sin un mic real. La impl real
    (`GoogleCloudSTT`) reemplaza esta clase en build_pi_application
    cuando hay credenciales."""

    canned_text: str = "estoy aquí"

    def transcribe(self, audio: AudioBuffer) -> TranscriptResult:
        return TranscriptResult(
            text=self.canned_text,
            confidence=0.0,
            language="es-CL",
        )


@dataclass
class _CannedTTS:
    """TTS fake — devuelve un buffer silencioso del tamaño correcto."""

    def synthesize(self, text: str) -> SynthesisResult:
        audio = AudioBuffer(
            data=b"\x00" * 1024,
            sample_rate=22050,
            encoding="MP3",
        )
        return SynthesisResult(
            audio=audio,
            voice_name="canned-dev",
            text_synthesized=text,
        )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


@dataclass
class Application:
    settings: Settings
    db: Database
    orchestrator: Orchestrator
    sync: SyncCoordinator
    crisis_protocol: CrisisProtocol
    leds: LEDController
    servos: ServoController
    event_bus: HardwareEventBus
    capture: AudioCaptureSource
    playback: AudioPlaybackSink
    wake_word: WakeWordDetector
    retriever: Retriever
    stt: STTClient
    tts: TTSClient
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        try:
            for resource in (
                self.orchestrator,
                self.sync,
                self.crisis_protocol,
                self.leds,
                self.servos,
                self.event_bus,
                self.capture,
                self.playback,
                self.wake_word,
                self.stt,
                self.tts,
            ):
                _close_if_available(resource)
        finally:
            self.db.close()
            self._closed = True


def _close_if_available(resource: object) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_dev_application(settings: Settings) -> Application:
    """Compone Application con fakes — sin tocar GPIO ni APIs cloud reales."""
    _ensure_parent_dir(settings.sqlite_path)
    # Misma apertura que build_pi_application: con clave configurada la base
    # local puede estar cifrada (p. ej. una Pi con RAKO_ENV=dev) y abrirla
    # sin clave falla con "file is not a database".
    db = Database.open(settings.sqlite_path, key=settings.sqlite_encryption_key)

    # Hardware
    leds = FakeLEDController()
    servos = FakeServoController()
    event_bus = InMemoryHardwareEventBus()
    capture = InMemoryCapture(audio=_silent_audio())
    playback = InMemoryPlayback()

    # Voz
    wake_word = SubstringWakeWordDetector(settings.wake_words_tuple)

    # Crisis collaborators (logging-only en dev)
    crisis_voice = _LoggingVoicePlayer()
    crisis_lighting = CrisisLightingAdapter(leds)
    crisis_notifier = _LoggingNotifier()
    protocol = CrisisProtocol(
        voice=crisis_voice,
        lighting=crisis_lighting,
        notifier=crisis_notifier,
        journal=db.crisis_journal,
    )

    # RAG: si hay índice ChromaDB persistido, usarlo; sino fallback in-memory.
    retriever = _build_retriever(settings)

    # LLM
    llm: LLMClient = _build_llm_client(settings)

    # Orchestrator
    orchestrator = Orchestrator(
        retriever=retriever,
        llm=llm,
        protocol=protocol,
    )

    # Sync (Firebase fake — el real se enchufa al provisionar)
    queue = SyncQueue(db._conn)  # type: ignore[attr-defined]
    firebase: FirebaseClient = FakeFirebaseClient()
    sync_coord = SyncCoordinator(queue=queue, client=firebase)

    return Application(
        settings=settings,
        db=db,
        orchestrator=orchestrator,
        sync=sync_coord,
        crisis_protocol=protocol,
        leds=leds,
        servos=servos,
        event_bus=event_bus,
        capture=capture,
        playback=playback,
        wake_word=wake_word,
        retriever=retriever,
        stt=_CannedSTT(),
        tts=_CannedTTS(),
    )


def build_pi_application(settings: Settings) -> Application:
    """Compone Application con impls reales para la Pi.

    Cada lib (gpiozero, neopixel, sounddevice) lazy-importa. Si una
    falla (e.g. corremos el binario en mac), caemos al fake equivalente
    para no crashear — útil para tests y para arrancar el binario en
    un entorno sin algunas piezas.
    """
    _ensure_parent_dir(settings.sqlite_path)
    db = Database.open(settings.sqlite_path, key=settings.sqlite_encryption_key)

    leds: LEDController = _try_real_leds() or FakeLEDController()
    servos: ServoController = _try_real_servos() or FakeServoController()
    event_bus = InMemoryHardwareEventBus()
    capture: AudioCaptureSource = _try_real_capture() or InMemoryCapture(audio=_silent_audio())
    playback: AudioPlaybackSink = _try_real_playback() or InMemoryPlayback()

    wake_word = SubstringWakeWordDetector(settings.wake_words_tuple)

    crisis_voice = _LoggingVoicePlayer()
    crisis_lighting = CrisisLightingAdapter(leds)
    # Notificador REAL del contacto de confianza: WhatsApp con
    # consentimiento registrado. Sin credenciales cloud usa el cliente en
    # memoria (equivalente a solo-log, sin efectos externos).
    crisis_notifier = WhatsAppCrisisNotifier(db=db, client=_build_whatsapp_client(settings))
    protocol = CrisisProtocol(
        voice=crisis_voice,
        lighting=crisis_lighting,
        notifier=crisis_notifier,
        journal=db.crisis_journal,
    )

    retriever = _build_retriever(settings)
    llm: LLMClient = _build_llm_client(settings)

    orchestrator = Orchestrator(
        retriever=retriever,
        llm=llm,
        protocol=protocol,
    )

    queue = SyncQueue(db._conn)  # type: ignore[attr-defined]
    firebase: FirebaseClient = FakeFirebaseClient()
    sync_coord = SyncCoordinator(queue=queue, client=firebase)

    stt: STTClient = _try_real_stt(settings) or _CannedSTT()
    tts: TTSClient = _try_real_tts(settings) or _CannedTTS()

    return Application(
        settings=settings,
        db=db,
        orchestrator=orchestrator,
        sync=sync_coord,
        crisis_protocol=protocol,
        leds=leds,
        servos=servos,
        event_bus=event_bus,
        capture=capture,
        playback=playback,
        wake_word=wake_word,
        retriever=retriever,
        stt=stt,
        tts=tts,
    )


def _try_real_leds() -> LEDController | None:
    # ReSpeaker 2-Mics Pi HAT uses I2S pins, including GPIO18 (PCM_CLK).
    # Driving NeoPixel/PWM on GPIO18 breaks microphone capture. Keep real LEDs
    # disabled until Rako has a non-conflicting LED pin/controller configured.
    return None


def _try_real_servos() -> ServoController | None:
    try:  # pragma: no cover - only loads on Pi
        from hardware.servos_real import create_pi_servos

        return create_pi_servos(head_pin=12, ear_pin=13)
    except Exception:
        _log.warning("real servo controller unavailable; falling back to fake", exc_info=True)
        return None


def _try_real_capture() -> AudioCaptureSource | None:
    try:  # pragma: no cover - only loads on Pi
        from hardware.audio_real import create_pi_capture

        return create_pi_capture()
    except Exception:
        _log.warning("real audio capture unavailable; falling back to fake", exc_info=True)
        return None


def _try_real_playback() -> AudioPlaybackSink | None:
    try:  # pragma: no cover - only loads on Pi
        from hardware.audio_real import create_pi_playback

        return create_pi_playback()
    except Exception:
        _log.warning("real audio playback unavailable; falling back to fake", exc_info=True)
        return None


def _ensure_google_credentials_env(settings: Settings) -> None:
    """Propaga la ruta de credenciales al entorno del proceso.

    Las libs de Google leen `GOOGLE_APPLICATION_CREDENTIALS` de `os.environ`,
    no del objeto `Settings`. Si solo está en `.env`, la auth falla.
    """
    path = settings.google_application_credentials
    if path and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path


def _try_real_stt(settings: Settings) -> STTClient | None:
    """Construye el STT real: cloud primario + whisper.cpp local si está
    configurado (cadena FallbackSTT — sin internet, Rako sigue oyendo)."""
    primary = _try_cloud_stt(settings)
    local = _try_whisper_cpp_stt(settings)
    if primary is not None and local is not None:
        return FallbackSTT((primary, local))
    return primary or local


def _try_whisper_cpp_stt(settings: Settings) -> STTClient | None:
    if not settings.whisper_cpp_bin or not settings.whisper_cpp_model:
        return None
    if not Path(settings.whisper_cpp_model).exists():
        _log.warning(
            "whisper.cpp model not found at %s; offline STT off", settings.whisper_cpp_model
        )
        return None
    return WhisperCppSTT(
        binary_path=settings.whisper_cpp_bin,
        model_path=settings.whisper_cpp_model,
        language=settings.google_stt_language.split("-")[0],
    )


def _try_cloud_stt(settings: Settings) -> STTClient | None:
    """STT cloud seleccionado.

    `openai_whisper` suele transcribir mejor nombres raros/acentos que Google.
    Google queda disponible como fallback estable si Whisper no está configurado.
    """
    if settings.stt_provider == "openai_whisper":
        whisper = _try_openai_whisper_stt(settings)
        if whisper is not None:
            return whisper
    return _try_google_stt(settings)


def _try_google_stt(settings: Settings) -> STTClient | None:
    if not settings.google_application_credentials:
        return None
    _ensure_google_credentials_env(settings)
    try:  # pragma: no cover - only with google-cloud-speech installed
        from google.cloud.speech_v1 import SpeechClient

        client = SpeechClient()
        return GoogleCloudSTT(client=client, language=settings.google_stt_language)
    except Exception:  # pragma: no cover - lib missing or auth failure
        _log.warning("Google Cloud STT init failed; falling back", exc_info=True)
        return None


def _try_openai_whisper_stt(settings: Settings) -> STTClient | None:
    if not settings.openai_api_key:
        return None
    try:  # pragma: no cover - requires openai at runtime
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        return OpenAIWhisperSTT(
            client=client,
            model=settings.openai_stt_model,
            language=settings.google_stt_language,
        )
    except Exception:  # pragma: no cover - lib missing or runtime init failure
        _log.warning("OpenAI Whisper STT init failed; falling back to Google", exc_info=True)
        return None


def _try_real_tts(settings: Settings) -> TTSClient | None:
    """Construye el TTS real. ElevenLabs es la voz principal y Google el
    fallback; con más de un candidato disponible se arma una cadena
    `FallbackTTS` para degradar también en runtime (no solo al iniciar)."""
    chain = _build_tts_chain(settings)
    if not chain:
        return None
    if len(chain) == 1:
        return chain[0]
    return FallbackTTS(chain)


def _build_whatsapp_client(settings: Settings) -> WhatsAppClient:
    """Mismo criterio que la API móvil (mobile/deps.py): cloud real solo
    con credenciales completas; si no, cliente en memoria (sin red)."""
    if (
        settings.whatsapp_client == "cloud"
        and settings.whatsapp_cloud_access_token
        and settings.whatsapp_cloud_phone_number_id
    ):
        return WhatsAppCloudClient(
            access_token=settings.whatsapp_cloud_access_token,
            phone_number_id=settings.whatsapp_cloud_phone_number_id,
            api_version=settings.whatsapp_cloud_api_version,
            timeout_s=settings.whatsapp_cloud_timeout_s,
        )
    return InMemoryWhatsAppClient()


def _build_tts_chain(settings: Settings) -> tuple[TTSClient, ...]:
    candidates: list[TTSClient | None] = []
    if settings.tts_provider == "elevenlabs":
        candidates.append(_try_elevenlabs_tts(settings))
    candidates.append(_try_google_tts(settings))
    # Último eslabón: frases curadas pre-sintetizadas en disco (offline).
    # Solo entra si el operador corrió rako-pregen-tts (cache no vacío).
    prerecorded = PrerecordedTTS(Path(settings.tts_cache_dir))
    if prerecorded.entry_count() > 0:
        candidates.append(prerecorded)
    return tuple(client for client in candidates if client is not None)


def _try_elevenlabs_tts(settings: Settings) -> TTSClient | None:
    if not settings.elevenlabs_api_key:
        return None
    try:  # pragma: no cover - requires httpx at runtime
        import httpx

        return ElevenLabsTTS(
            http_client=httpx.Client(),
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            model=settings.elevenlabs_model,
            stability=settings.elevenlabs_stability,
            similarity_boost=settings.elevenlabs_similarity_boost,
            timeout_s=settings.anthropic_timeout_s,
        )
    except Exception:  # pragma: no cover - lib missing or runtime init failure
        _log.warning("ElevenLabs TTS init failed; falling back to Google", exc_info=True)
        return None


def _try_google_tts(settings: Settings) -> TTSClient | None:
    if not settings.google_application_credentials:
        return None
    creds_path = Path(settings.google_application_credentials)
    if not creds_path.exists():
        _log.info("Google TTS fallback disabled: credentials file %s not found", creds_path)
        return None
    _ensure_google_credentials_env(settings)
    try:  # pragma: no cover - only with google-cloud-texttospeech installed
        from google.cloud.texttospeech_v1 import TextToSpeechClient

        client = TextToSpeechClient()
        return GoogleCloudTTS(
            client=client,
            voice_name=settings.google_tts_voice,
            language_code=settings.google_stt_language,
            speaking_rate=settings.google_tts_speaking_rate,
        )
    except Exception:  # pragma: no cover - lib missing or auth failure
        _log.warning("Google Cloud TTS init failed; no TTS available", exc_info=True)
        return None


def _build_retriever(settings: Settings) -> Retriever:
    """Usa ChromaDB si la colección existe, sino InMemoryRetriever vacío."""
    if not Path(settings.chroma_db_path).exists():
        return InMemoryRetriever([])
    return ChromaRetriever(
        db_path=settings.chroma_db_path,
        collection_name=settings.chroma_collection,
        embedder=build_embedder(settings.rag_embedding_model),
    )


def _build_llm_client(settings: Settings) -> LLMClient:
    system_prompt = _load_system_prompt(settings.obsidian_vault_path)
    if settings.llm_provider == "openai":
        openai = _try_openai_llm(settings, system_prompt)
        if openai is not None:
            return openai
        return _try_anthropic_llm(settings, system_prompt) or _CannedLLMClient()

    return _try_anthropic_llm(settings, system_prompt) or _CannedLLMClient()


def _try_openai_llm(settings: Settings, system_prompt: str) -> LLMClient | None:
    if not settings.openai_api_key:
        return None
    try:  # pragma: no cover - requires httpx at runtime
        import httpx

        return OpenAILLMClient(
            http_client=httpx.Client(),
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tokens=settings.anthropic_max_tokens,
            system_prompt=system_prompt,
            timeout_s=settings.anthropic_timeout_s,
        )
    except Exception:  # pragma: no cover - lib missing or runtime init failure
        _log.warning("OpenAI LLM init failed; falling back to Anthropic", exc_info=True)
        return None


def _try_anthropic_llm(settings: Settings, system_prompt: str) -> LLMClient | None:
    if not settings.anthropic_api_key:
        return None

    anthropic_client = Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.anthropic_timeout_s,
    )
    return AnthropicLLMClient(
        client=anthropic_client,
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        system_prompt=system_prompt,
    )


def _load_system_prompt(vault_path: str) -> str:
    note = Path(vault_path) / "system_prompt_rako.md"
    if not note.exists():
        return _FALLBACK_SYSTEM_PROMPT
    try:
        return extract_system_prompt(note.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return _FALLBACK_SYSTEM_PROMPT


def _silent_audio() -> AudioBuffer:
    return AudioBuffer(data=b"\x00" * 32000, sample_rate=16000, encoding="LINEAR16")


def _ensure_parent_dir(path: str) -> None:
    if path == ":memory:":
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
