"""Bootstrap del cerebro — arma el grafo de dependencias.

`build_dev_application(settings)` compone una `Application` con fakes
para todo lo que requiere hardware o credenciales reales (cloud APIs,
GPIO). Útil para CI, demos y desarrollo en mac.

Una versión `build_pi_application` se agregará al provisionar la Pi —
intercambia los fakes por las impls reales (`gpiozero`, `sounddevice`,
`google-cloud-speech`, `firebase-admin`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anthropic import Anthropic

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
)
from orchestrator.orchestrator import Orchestrator
from orchestrator.prompts import extract_system_prompt
from rag.chroma_retriever import ChromaRetriever
from rag.client import InMemoryRetriever, Retriever
from safety.protocol import CrisisProtocol
from safety.types import CrisisSignal
from sync.coordinator import SyncCoordinator
from sync.firebase_client import FakeFirebaseClient, FirebaseClient
from sync.queue import SyncQueue
from voice.audio_io import AudioCaptureSource, AudioPlaybackSink
from voice.types import AudioBuffer
from voice.wake_word import SubstringWakeWordDetector, WakeWordDetector

_FALLBACK_SYSTEM_PROMPT = (
    "Eres Rako: un asistente de acompañamiento emocional para "
    "estudiantes universitarios. Tono adulto, directo, cálido. "
    "Validar antes de sugerir. Respuestas cortas (2-4 oraciones)."
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

    def close(self) -> None:
        self.db.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_dev_application(settings: Settings) -> Application:
    """Compone Application con fakes — sin tocar GPIO ni APIs cloud reales."""
    _ensure_parent_dir(settings.sqlite_path)
    db = Database.open(settings.sqlite_path)

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
    crisis_notifier = _LoggingNotifier()
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
    )


def _try_real_leds() -> LEDController | None:
    try:  # pragma: no cover - only loads on Pi
        from hardware.leds_neopixel import create_pi_neopixel_controller

        return create_pi_neopixel_controller(pin=18, count=12)
    except Exception:
        return None


def _try_real_servos() -> ServoController | None:
    try:  # pragma: no cover - only loads on Pi
        from hardware.servos_real import create_pi_servos

        return create_pi_servos(head_pin=12, ear_pin=13)
    except Exception:
        return None


def _try_real_capture() -> AudioCaptureSource | None:
    try:  # pragma: no cover - only loads on Pi
        from hardware.audio_real import create_pi_capture

        return create_pi_capture()
    except Exception:
        return None


def _try_real_playback() -> AudioPlaybackSink | None:
    try:  # pragma: no cover - only loads on Pi
        from hardware.audio_real import create_pi_playback

        return create_pi_playback()
    except Exception:
        return None


def _build_retriever(settings: Settings) -> Retriever:
    """Usa ChromaDB si la colección existe, sino InMemoryRetriever vacío."""
    if not Path(settings.chroma_db_path).exists():
        return InMemoryRetriever([])
    return ChromaRetriever(
        db_path=settings.chroma_db_path,
        collection_name=settings.chroma_collection,
    )


def _build_llm_client(settings: Settings) -> LLMClient:
    if not settings.anthropic_api_key:
        return _CannedLLMClient()

    anthropic_client = Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.anthropic_timeout_s,
    )
    system_prompt = _load_system_prompt(settings.obsidian_vault_path)
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
