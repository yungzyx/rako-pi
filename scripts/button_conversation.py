"""Trigger a Rako conversation from a physical GPIO button.

Default target: ReSpeaker 2-Mics Pi HAT user button, commonly wired to BCM GPIO17.

Flow:
    startup: warm up app (Chroma/DB/clients) so the first turn isn't slow
    button press -> capture mic audio -> STT -> orchestrator -> TTS -> optional playback

Input audio is never persisted. Only TTS output may be written to /tmp for playback.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/button_conversation.py --no-playback
    PYTHONPATH=src .venv/bin/python scripts/button_conversation.py --pin 17
"""

from __future__ import annotations

import argparse
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bootstrap import build_pi_application
from config import Settings
from hardware.oled_runtime import OledEyeController
from hardware.oled_states import RakoVisualState
from orchestrator.orchestrator import TurnInput, TurnKind
from orchestrator.turn_session import TurnSession
from orchestrator.types import default_user_context
from productivity.runtime import maybe_start_focus_from_transcript
from safety.detector import detect_crisis
from safety.scope import mentions_mental_health_topic
from safety.triage import TriageLevel, triage_turn
from safety.types import CrisisInput
from voice.types import AudioBuffer

_DEFAULT_BUTTON_PIN = 17
_DEFAULT_CAPTURE_SECONDS = 7.0
_DEFAULT_AUDIO_OUTPUT_DEVICE = "plughw:seeed2micvoicec,0"
_DEFAULT_GPIO_CHIP = "gpiochip0"
_DEFAULT_CAPTURE_DEVICE = "plughw:seeed2micvoicec,0"
_DEFAULT_CAPTURE_RATE = 16000
_DEFAULT_PLAYBACK_WARMUP_SECONDS = 0.15
_DEFAULT_CUE_VOLUME = 0.14
_DEFAULT_END_SILENCE_SECONDS = 0.8
_DEFAULT_VAD_THRESHOLD = 1400
_DEFAULT_VAD_FRAME_MS = 100

# Feedback hablado cuando el STT no entendió nada — sin voz, el usuario solo
# ve ojos de error y no sabe si repetir o esperar.
_DID_NOT_HEAR_TEXT = "No te escuché bien. ¿Me lo repites?"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Use a GPIO button to start a Rako turn")
    parser.add_argument(
        "--pin",
        type=int,
        default=_DEFAULT_BUTTON_PIN,
        help=f"BCM GPIO pin for button (default: {_DEFAULT_BUTTON_PIN})",
    )
    parser.add_argument(
        "--gpio-chip",
        default=_DEFAULT_GPIO_CHIP,
        help=f"GPIO chip for gpiomon backend (default: {_DEFAULT_GPIO_CHIP})",
    )
    parser.add_argument(
        "--backend",
        choices=("gpiomon", "gpiozero", "auto"),
        default="gpiomon",
        help="Button backend. Default is gpiomon because RPi.GPIO edge detection fails on newer kernels.",
    )
    parser.add_argument(
        "--capture-seconds",
        type=float,
        default=_DEFAULT_CAPTURE_SECONDS,
        help=f"Seconds to listen after button press (default: {_DEFAULT_CAPTURE_SECONDS})",
    )
    parser.add_argument(
        "--capture-device",
        default=_DEFAULT_CAPTURE_DEVICE,
        help=f"ALSA arecord device for mic capture (default: {_DEFAULT_CAPTURE_DEVICE})",
    )
    parser.add_argument(
        "--capture-rate",
        type=int,
        default=_DEFAULT_CAPTURE_RATE,
        help=f"Sample rate for STT capture (default: {_DEFAULT_CAPTURE_RATE})",
    )
    parser.add_argument(
        "--audio-device",
        default=_DEFAULT_AUDIO_OUTPUT_DEVICE,
        help=f"ALSA device for mpg123 playback (default: {_DEFAULT_AUDIO_OUTPUT_DEVICE})",
    )
    parser.add_argument(
        "--oled",
        action="store_true",
        help="Drive OLED eye expressions during the turn",
    )
    parser.add_argument(
        "--no-cues",
        action="store_true",
        help="Disable short start/end sounds around a button turn",
    )
    parser.add_argument(
        "--cue-volume",
        type=float,
        default=_DEFAULT_CUE_VOLUME,
        help=f"Cue sound volume from 0.0 to 1.0 (default: {_DEFAULT_CUE_VOLUME})",
    )
    parser.add_argument(
        "--playback-warmup-seconds",
        type=float,
        default=_DEFAULT_PLAYBACK_WARMUP_SECONDS,
        help=(
            "Seconds of silence to play before TTS so the audio device does not cut "
            f"the first syllable (default: {_DEFAULT_PLAYBACK_WARMUP_SECONDS})"
        ),
    )
    parser.add_argument(
        "--end-silence-seconds",
        type=float,
        default=_DEFAULT_END_SILENCE_SECONDS,
        help=(
            "Silence required after the last detected word before sending audio to STT "
            f"(default: {_DEFAULT_END_SILENCE_SECONDS})"
        ),
    )
    parser.add_argument(
        "--vad-threshold",
        type=int,
        default=_DEFAULT_VAD_THRESHOLD,
        help=f"PCM16 RMS threshold used for speech detection (default: {_DEFAULT_VAD_THRESHOLD})",
    )
    parser.add_argument(
        "--no-vad-trim",
        action="store_true",
        help="Disable end-of-turn VAD trimming before STT",
    )
    parser.add_argument(
        "--no-focus-countdown",
        action="store_true",
        help="Do not launch the OLED/spoken countdown after focus intents",
    )
    parser.add_argument(
        "--no-playback",
        action="store_true",
        help="Do not try speaker playback; only print and save TTS output",
    )
    parser.add_argument(
        "--no-chunked-tts",
        action="store_true",
        help="Synthesize the full reply in one call instead of speaking sentence by sentence",
    )
    parser.add_argument(
        "--no-stream-tts",
        action="store_true",
        help="Disable provider audio streaming; fall back to chunked/single synthesis",
    )
    args = parser.parse_args(argv)

    if args.capture_seconds <= 0:
        parser.error("--capture-seconds must be positive")
    if args.capture_rate <= 0:
        parser.error("--capture-rate must be positive")
    if args.playback_warmup_seconds < 0:
        parser.error("--playback-warmup-seconds cannot be negative")
    if args.end_silence_seconds < 0:
        parser.error("--end-silence-seconds cannot be negative")
    if args.vad_threshold < 0:
        parser.error("--vad-threshold cannot be negative")
    if not 0 <= args.cue_volume <= 1:
        parser.error("--cue-volume must be between 0.0 and 1.0")

    app_holder: dict[str, Any] = {"app": None, "session": None}
    eyes = OledEyeController(enabled=args.oled, project_root=Path(__file__).resolve().parents[1])
    eyes.set_state(RakoVisualState.READY)

    print(f"Rako button listener ready on BCM GPIO{args.pin}.", flush=True)
    print(
        "Press the ReSpeaker button, then speak after 'Escuchando...'. Ctrl+C to stop.", flush=True
    )

    # Warm-up al arranque: pagar el init ahora (antes de que nadie hable) para
    # que el PRIMER turno sea tan rápido como los siguientes. Si falla, el
    # listener igual arranca y el init se reintenta perezosamente al primer botón.
    try:
        _ensure_app_ready(app_holder=app_holder, eyes=eyes)
        eyes.set_state(RakoVisualState.READY)
    except Exception as exc:
        print(
            f"No pude inicializar Rako al arranque ({exc}); reintento al primer botón.", flush=True
        )

    def handle_press() -> None:
        _handle_press(
            app_holder=app_holder, eyes=eyes, capture_seconds=args.capture_seconds, args=args
        )

    try:
        _run_button_loop(
            pin=args.pin,
            gpio_chip=args.gpio_chip,
            backend=args.backend,
            on_press=handle_press,
        )
    except KeyboardInterrupt:
        print("\nDetenido.", flush=True)
    finally:
        eyes.close()
        app = app_holder.get("app")
        if app is not None:
            app.close()
    return 0


def _run_button_loop(
    *, pin: int, gpio_chip: str, backend: str, on_press: Callable[[], None]
) -> None:
    if backend == "gpiomon":
        _run_gpiomon_loop(pin=pin, gpio_chip=gpio_chip, on_press=on_press)
        return
    if backend == "gpiozero":
        _run_gpiozero_loop(pin=pin, on_press=on_press)
        return

    try:
        _run_gpiozero_loop(pin=pin, on_press=on_press)
    except Exception as exc:
        print(f"gpiozero button backend failed ({exc}); falling back to gpiomon.", flush=True)
        _run_gpiomon_loop(pin=pin, gpio_chip=gpio_chip, on_press=on_press)


def _run_gpiozero_loop(*, pin: int, on_press: Callable[[], None]) -> None:
    from gpiozero import Button

    button = Button(pin, pull_up=True, bounce_time=0.05)
    button.when_pressed = on_press
    while True:
        input()


def _run_gpiomon_loop(*, pin: int, gpio_chip: str, on_press: Callable[[], None]) -> None:
    if shutil.which("gpiomon") is None:
        raise RuntimeError("gpiomon is not installed")

    print(f"Waiting with gpiomon on {gpio_chip} line {pin} (falling edge).", flush=True)
    while True:
        command = [
            "gpiomon",
            "--chip",
            gpio_chip,
            "--edges",
            "falling",
            "--bias",
            "pull-up",
            "--debounce-period",
            "50ms",
            "--num-events",
            "1",
            str(pin),
        ]
        subprocess.run(command, check=True)
        on_press()


def _ensure_app_ready(*, app_holder: dict[str, Any], eyes: OledEyeController) -> None:
    """Inicializa la app y la sesión una sola vez (idempotente).

    Se llama al ARRANQUE para que el primer turno no pague los ~5 s de init
    (Chroma, embeddings, DB, clientes cloud) DESPUÉS de que el usuario ya
    habló — ese hueco de silencio caía en el peor momento. Queda como fallback
    perezoso dentro del turno por si el arranque falló. Pipeline de turno
    compartido con RunLoop: memoria + triage + persistencia con gate de
    privacidad (orchestrator/turn_session).
    """
    if app_holder["app"] is not None:
        return
    eyes.set_state(RakoVisualState.STARTING)
    print("Inicializando Rako...", flush=True)
    init_started = time.monotonic()
    app = build_pi_application(Settings())
    session = TurnSession(db=app.db, settings=app.settings)
    session.restore_recent_memory()
    app_holder["app"] = app
    app_holder["session"] = session
    print(f"Tiempo inicialización: {time.monotonic() - init_started:.2f}s", flush=True)


def _handle_press(
    *,
    app_holder: dict[str, Any],
    eyes: OledEyeController,
    capture_seconds: float,
    args: argparse.Namespace,
) -> None:
    turn_started = time.monotonic()
    print("\nBotón detectado. Escuchando...", flush=True)
    eyes.set_state(RakoVisualState.LISTENING)
    _play_cue(kind="listen_start", args=args)
    try:
        capture_started = time.monotonic()
        audio = _capture_with_arecord(
            device=args.capture_device,
            sample_rate=args.capture_rate,
            seconds=capture_seconds,
            end_silence_seconds=args.end_silence_seconds,
            vad_threshold=args.vad_threshold,
            vad_trim=not args.no_vad_trim,
        )
        print(f"Tiempo captura: {time.monotonic() - capture_started:.2f}s", flush=True)
        eyes.set_state(RakoVisualState.CAPTURED)
        _play_cue(kind="listen_end", args=args)
        _ensure_app_ready(app_holder=app_holder, eyes=eyes)
        app = app_holder["app"]
        eyes.set_state(RakoVisualState.TRANSCRIBING)
        stt_started = time.monotonic()
        transcript = app.stt.transcribe(audio).text.strip()
        print(f"Tiempo STT: {time.monotonic() - stt_started:.2f}s", flush=True)
    except Exception as exc:
        eyes.set_state(RakoVisualState.ERROR)
        print(f"No pude capturar/transcribir: {exc}", flush=True)
        # Feedback hablado en vez de silencio total: STT vacío, ruido o red
        # caída son las fallas más comunes y dejaban al usuario sin saber si
        # repetir o esperar. Si la voz también falla, caemos a la pausa breve.
        app = app_holder.get("app")
        spoke = False
        if app is not None:
            try:
                _synthesize_and_maybe_play(app=app, text=_DID_NOT_HEAR_TEXT, eyes=eyes, args=args)
                spoke = True
            except Exception:
                spoke = False
        if not spoke:
            time.sleep(1)
        eyes.set_state(RakoVisualState.READY)
        return

    if not transcript:
        eyes.set_state(RakoVisualState.ERROR)
        print("No escuché una frase clara.", flush=True)
        _synthesize_and_maybe_play(app=app, text=_DID_NOT_HEAR_TEXT, eyes=eyes, args=args)
        eyes.set_state(RakoVisualState.READY)
        return

    print(f"Tú: {transcript}", flush=True)
    now = datetime.now(UTC)
    eyes.set_state(RakoVisualState.THINKING)
    session: TurnSession = app_holder["session"]

    guardrail_result = _guardrail_result_for_transcript(app=app, transcript=transcript, now=now)
    if guardrail_result is not None:
        print(f"Rako: {guardrail_result.text}", flush=True)
        _synthesize_and_maybe_play(app=app, text=guardrail_result.text, eyes=eyes, args=args)
        eyes.set_state(RakoVisualState.READY)
        return

    remember_confirmation = session.try_remember_command(transcript)
    if remember_confirmation is not None:
        print(f"Rako: {remember_confirmation}", flush=True)
        _synthesize_and_maybe_play(app=app, text=remember_confirmation, eyes=eyes, args=args)
        eyes.set_state(RakoVisualState.READY)
        return

    music_response = _handle_music_intent(transcript, args=args)
    if music_response is not None:
        print(f"Rako: {music_response}", flush=True)
        _synthesize_and_maybe_play(app=app, text=music_response, eyes=eyes, args=args)
        session.add_exchange(user=transcript, rako=music_response)
        eyes.set_state(RakoVisualState.READY)
        return

    focus = maybe_start_focus_from_transcript(transcript, db=app.db, now=now)
    if focus is not None:
        if focus.needs_duration or focus.session is None:
            eyes.set_state(RakoVisualState.THINKING)
            print(f"Rako: {focus.response_text}", flush=True)
            _synthesize_and_maybe_play(app=app, text=focus.response_text, eyes=eyes, args=args)
            session.add_exchange(user=transcript, rako=focus.response_text)
            eyes.set_state(RakoVisualState.READY)
            return
        eyes.set_state(RakoVisualState.FOCUS_RUNNING)
        print(f"Rako: {focus.response_text}", flush=True)
        _synthesize_and_maybe_play(app=app, text=focus.response_text, eyes=eyes, args=args)
        session.add_exchange(user=transcript, rako=focus.response_text)
        if not args.no_focus_countdown:
            eyes.close()
            _launch_focus_countdown(focus=focus, args=args)
        else:
            eyes.set_state(RakoVisualState.READY)
        return

    turn = session.build_turn_input(transcript, now=now)
    llm_started = time.monotonic()
    result = app.orchestrator.handle_turn(turn)
    print(f"Tiempo orquestador/LLM: {time.monotonic() - llm_started:.2f}s", flush=True)
    print(f"Tiempo total antes de responder: {time.monotonic() - turn_started:.2f}s", flush=True)
    print(f"Rako: {result.text}", flush=True)
    _synthesize_and_maybe_play(app=app, text=result.text, eyes=eyes, args=args)
    session.complete_turn(transcript=transcript, result=result, now=now)
    suggestion = session.suggest_preference(transcript, result)
    if suggestion is not None:
        print(f"Rako: {suggestion}", flush=True)
        _synthesize_and_maybe_play(app=app, text=suggestion, eyes=eyes, args=args)
    eyes.set_state(RakoVisualState.READY)


def _guardrail_result_for_transcript(*, app: Any, transcript: str, now: datetime) -> Any | None:
    signal = detect_crisis(
        CrisisInput(
            transcript=transcript,
            emotion_history=(),
            panic_button=None,
            last_high_distress_at=None,
            last_interaction_at=None,
            now=now,
        )
    )
    # Este guard corre ANTES de los intent handlers locales (música, foco) para
    # que una crisis o una redirección de alcance clínico no queden enmascaradas
    # por ellos. Solo nos interesan esos dos desenlaces —ambos CURADOS, sin LLM—.
    # Decidimos de forma determinística: si el turno terminaría en el LLM, NO lo
    # corremos acá. Antes se llamaba a `handle_turn` siempre que hubiera una
    # palabra de salud mental, gatillando una llamada RAG+LLM que se descartaba
    # y luego el turno real volvía a llamar al LLM: doble latencia en justo los
    # turnos de ansiedad académica ("estoy con ansiedad por la prueba").
    if not signal.should_bypass_llm:
        if not mentions_mental_health_topic(transcript):
            return None
        if triage_turn(transcript).level is not TriageLevel.CLINICAL_SCOPE:
            return None

    turn = TurnInput(
        transcript=transcript,
        emotion=None,
        panic_button=None,
        emotion_history=(),
        last_high_distress_at=None,
        last_interaction_at=None,
        user_context=default_user_context(now),
        now=now,
    )
    result = app.orchestrator.handle_turn(turn)
    if result.kind in {TurnKind.CRISIS_PROTOCOL, TurnKind.SCOPE_REDIRECT}:
        return result
    return None


def _handle_music_intent(transcript: str, *, args: argparse.Namespace) -> str | None:
    text = transcript.lower()
    mentions_music = any(
        word in text for word in ("música", "musica", "chill", "relajante", "lofi")
    )
    if not mentions_music:
        return None
    command = [sys.executable, str(Path(__file__).resolve().parent / "music_mode.py")]
    if any(
        phrase in text
        for phrase in (
            "para la música",
            "detén la música",
            "apaga la música",
            "stop music",
            "sin música",
        )
    ):
        subprocess.run([*command, "stop"], check=False)
        return "Listo, apagué la música."
    subprocess.run([*command, "start", "--audio-device", args.audio_device], check=False)
    return "Listo, puse un ambiente chill suave para estudiar. Si quieres que lo apague, dime: Rako, para la música."


def _launch_focus_countdown(*, focus: Any, args: argparse.Namespace) -> None:
    minutes = max(1, int(focus.session.duration.total_seconds() // 60))
    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "focus_countdown.py"),
        "--title",
        focus.session.task_title,
        "--minutes",
        str(minutes),
        "--audio-device",
        args.audio_device,
        "--cue-volume",
        str(args.cue_volume),
        "--playback-warmup-seconds",
        str(args.playback_warmup_seconds),
    ]
    if args.no_playback:
        command.append("--no-playback")
    if args.no_cues:
        command.append("--no-cues")
    if not args.oled:
        command.append("--no-oled")
    subprocess.Popen(command, cwd=str(Path(__file__).resolve().parents[1]))


# Trozos de habla: bajar la latencia percibida sintetizando y reproduciendo
# por oraciones — la primera frase suena mientras el resto se sintetiza en
# paralelo. Fragmentos muy cortos se fusionan para no cortar la prosodia.
_SPEECH_CHUNK_MIN_CHARS = 60
_SPEECH_CHUNK_MAX_CHARS = 260


def _split_speech_chunks(
    text: str,
    *,
    min_chars: int = _SPEECH_CHUNK_MIN_CHARS,
    max_chars: int = _SPEECH_CHUNK_MAX_CHARS,
) -> list[str]:
    """Divide en trozos hablables por límites de oración.

    Nunca corta dentro de una oración; junta oraciones consecutivas hasta
    `min_chars` para evitar trozos de 2 palabras, y cierra el trozo al
    superar `max_chars`.
    """
    import re

    normalized = " ".join(text.strip().split())
    if not normalized:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", normalized) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
        if len(current) >= min_chars and len(current) <= max_chars:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def _resolve_stream_client(app: Any) -> Any | None:
    """Cliente TTS con soporte de streaming, directo o dentro de la cadena."""
    tts = app.tts
    if callable(getattr(tts, "synthesize_stream", None)):
        return tts
    stream_client = getattr(tts, "stream_client", None)
    if callable(stream_client):
        return stream_client()
    return None


def _try_streaming_playback(
    *, app: Any, text: str, eyes: OledEyeController | None, args: argparse.Namespace
) -> bool:
    """Reproduce audio a medida que llega del proveedor (latencia mínima).

    Devuelve True si el turno quedó hablado por esta vía. Cualquier fallo
    ANTES del primer byte cae en silencio al camino normal; un fallo a
    mitad de reproducción no se reintenta (ya sonó parcialmente).
    """
    client = _resolve_stream_client(app)
    if client is None:
        return False
    try:
        stream_started = time.monotonic()
        stream = client.synthesize_stream(text)
        first_chunk = next(stream, None)
        if first_chunk is None:
            return False
        print(
            f"Tiempo TTS (primer byte, streaming): {time.monotonic() - stream_started:.2f}s",
            flush=True,
        )
    except Exception as exc:
        print(f"Streaming TTS no disponible ({exc}); uso síntesis normal.", flush=True)
        return False

    _play_cue(kind="reply_start", args=args)
    _warm_up_audio_device(device=args.audio_device, seconds=args.playback_warmup_seconds)
    if eyes is not None:
        eyes.set_state(RakoVisualState.SPEAKING)
    player = subprocess.Popen(
        ["mpg123", "-q", "-o", "alsa", "-a", args.audio_device, "-"],
        stdin=subprocess.PIPE,
    )
    try:
        assert player.stdin is not None
        player.stdin.write(first_chunk)
        for chunk in stream:
            player.stdin.write(chunk)
        player.stdin.close()
        player.wait()
    except Exception as exc:
        print(f"Streaming TTS se cortó a mitad de la respuesta: {exc}", flush=True)
        player.kill()
    return True


def _synthesize_and_maybe_play(
    *, app: Any, text: str, eyes: OledEyeController | None = None, args: argparse.Namespace
) -> None:
    playback_available = not args.no_playback and shutil.which("mpg123") is not None
    if (
        playback_available
        and not args.no_stream_tts
        and _try_streaming_playback(app=app, text=text, eyes=eyes, args=args)
    ):
        return
    chunks = [text]
    if playback_available and not args.no_chunked_tts:
        chunks = _split_speech_chunks(text) or [text]

    try:
        tts_started = time.monotonic()
        synth = app.tts.synthesize(chunks[0])
        print(f"Tiempo TTS (primer trozo): {time.monotonic() - tts_started:.2f}s", flush=True)
    except Exception as exc:
        if eyes is not None:
            eyes.set_state(RakoVisualState.ERROR)
        print(f"No pude sintetizar voz: {exc}", flush=True)
        return

    out = Path("/tmp/rako-button-reply.mp3")
    out.write_bytes(synth.audio.data)
    print(f"Audio TTS guardado en {out}", flush=True)

    if args.no_playback:
        return
    if shutil.which("mpg123") is None:
        print("mpg123 no está instalado; no reproduzco audio automáticamente.", flush=True)
        return
    _play_cue(kind="reply_start", args=args)
    _warm_up_audio_device(device=args.audio_device, seconds=args.playback_warmup_seconds)
    if eyes is not None:
        eyes.set_state(RakoVisualState.SPEAKING)
    _play_chunks_pipelined(app=app, first=out, remaining=chunks[1:], args=args)


def _play_chunks_pipelined(
    *, app: Any, first: Path, remaining: list[str], args: argparse.Namespace
) -> None:
    """Reproduce el primer trozo mientras el siguiente se sintetiza aparte."""
    import threading

    current = first
    for index, chunk in enumerate(remaining, start=1):
        holder: dict[str, Any] = {}

        def _prefetch(text_chunk: str = chunk, into: dict[str, Any] = holder) -> None:
            try:
                into["synth"] = app.tts.synthesize(text_chunk)
            except Exception as exc:
                into["error"] = exc

        prefetch = threading.Thread(target=_prefetch, daemon=True)
        prefetch.start()
        _play_mp3(current, args=args)
        prefetch.join()
        if "synth" not in holder:
            print(f"No pude sintetizar el trozo {index + 1}: {holder.get('error')}", flush=True)
            return
        current = Path(f"/tmp/rako-button-reply-{index}.mp3")
        current.write_bytes(holder["synth"].audio.data)
    _play_mp3(current, args=args)


def _play_mp3(path: Path, *, args: argparse.Namespace) -> None:
    subprocess.run(["mpg123", "-q", "-o", "alsa", "-a", args.audio_device, str(path)], check=False)


def _play_cue(*, kind: str, args: argparse.Namespace) -> None:
    if args.no_playback or args.no_cues:
        return
    if shutil.which("aplay") is None:
        return
    path = _cue_path(kind=kind, volume=args.cue_volume)
    subprocess.run(["aplay", "-q", "-D", args.audio_device, str(path)], check=False)


def _cue_path(*, kind: str, volume: float) -> Path:
    path = Path(f"/tmp/rako-cue-{kind}-{volume:.2f}.wav")
    if path.exists():
        return path
    if kind == "listen_start":
        tones = ((700.0, 0.055), (940.0, 0.08))
    elif kind == "listen_end":
        tones = ((560.0, 0.055),)
    elif kind == "reply_start":
        tones = ((820.0, 0.045), (1040.0, 0.055))
    else:
        raise ValueError(f"unknown cue kind: {kind}")
    _write_tone_sequence(path=path, tones=tones, volume=volume)
    return path


def _write_tone_sequence(
    *, path: Path, tones: Sequence[tuple[float, float]], volume: float
) -> None:
    sample_rate = 44100
    frames = bytearray()
    amplitude = int(32767 * volume)
    for frequency, seconds in tones:
        frame_count = int(sample_rate * seconds)
        for i in range(frame_count):
            envelope = min(i / max(1, sample_rate * 0.01), 1.0)
            tail = min((frame_count - i) / max(1, sample_rate * 0.02), 1.0)
            sample = int(
                amplitude * envelope * tail * math.sin(2 * math.pi * frequency * i / sample_rate)
            )
            frames.extend(struct.pack("<h", sample))
        frames.extend(b"\x00\x00" * int(sample_rate * 0.035))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))


def _warm_up_audio_device(*, device: str, seconds: float) -> None:
    if seconds <= 0:
        return
    if shutil.which("aplay") is None:
        time.sleep(min(seconds, 0.5))
        return
    # Cacheado por duración (como los cues): su contenido solo depende de
    # `seconds`, así que reescribirlo en cada respuesta era I/O de disco al pedo.
    path = Path(f"/tmp/rako-playback-warmup-{seconds:.2f}.wav")
    if not path.exists():
        sample_rate = 44100
        frame_count = max(1, int(sample_rate * seconds))
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"\x00\x00" * frame_count)
    subprocess.run(["aplay", "-q", "-D", device, str(path)], check=False)
    time.sleep(0.05)


def _capture_with_arecord(
    *,
    device: str,
    sample_rate: int,
    seconds: float,
    end_silence_seconds: float = _DEFAULT_END_SILENCE_SECONDS,
    vad_threshold: int = _DEFAULT_VAD_THRESHOLD,
    vad_trim: bool = True,
) -> AudioBuffer:
    if shutil.which("arecord") is None:
        raise RuntimeError("arecord is not installed")

    if vad_trim:
        data, rate, channels = _capture_until_end_of_turn_with_arecord(
            device=device,
            sample_rate=sample_rate,
            max_seconds=seconds,
            end_silence_seconds=end_silence_seconds,
            threshold=vad_threshold,
            frame_ms=_DEFAULT_VAD_FRAME_MS,
        )
    else:
        data, rate, channels = _capture_fixed_duration_with_arecord(
            device=device,
            sample_rate=sample_rate,
            seconds=seconds,
        )

    samples = struct.unpack("<" + "h" * (len(data) // 2), data) if data else []
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) if samples else 0.0
    peak = max((abs(sample) for sample in samples), default=0)
    print(
        f"Audio capturado: {channels}ch {rate}Hz, rms={rms:.1f}, peak={peak}",
        flush=True,
    )
    if peak == 0:
        print("Aviso: el audio llegó en silencio total desde ALSA.", flush=True)
    data = _normalize_pcm16(data, target_peak=24_000)
    return AudioBuffer(data=data, sample_rate=rate, encoding="LINEAR16")


def _capture_fixed_duration_with_arecord(
    *, device: str, sample_rate: int, seconds: float
) -> tuple[bytes, int, int]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        command = [
            "arecord",
            "-q",
            "-D",
            device,
            "-f",
            "S16_LE",
            "-c",
            "1",
            "-r",
            str(sample_rate),
            "-d",
            str(max(1, math.ceil(seconds))),
            tmp.name,
        ]
        subprocess.run(command, check=True)
        with wave.open(tmp.name, "rb") as wav:
            data = wav.readframes(wav.getnframes())
            rate = wav.getframerate()
            channels = wav.getnchannels()
    return data, rate, channels


def _capture_until_end_of_turn_with_arecord(
    *,
    device: str,
    sample_rate: int,
    max_seconds: float,
    end_silence_seconds: float,
    threshold: int,
    frame_ms: int,
) -> tuple[bytes, int, int]:
    frame_samples = max(1, int(sample_rate * frame_ms / 1000))
    frame_bytes = frame_samples * 2
    command = [
        "arecord",
        "-q",
        "-D",
        device,
        "-f",
        "S16_LE",
        "-c",
        "1",
        "-r",
        str(sample_rate),
        "-t",
        "raw",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    chunks: list[bytes] = []
    voice_seen = False
    silence_after_voice = 0.0
    stopped_by_silence = False
    started = time.monotonic()
    silence_threshold = max(1, int(threshold * 0.55))
    print(
        f"VAD: voz >= {threshold} RMS, silencio < {silence_threshold} RMS",
        flush=True,
    )
    try:
        assert process.stdout is not None
        while time.monotonic() - started < max_seconds:
            chunk = process.stdout.read(frame_bytes)
            if not chunk:
                break
            chunks.append(chunk)
            samples = struct.unpack("<" + "h" * (len(chunk) // 2), chunk)
            rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
            if rms >= threshold:
                voice_seen = True
                silence_after_voice = 0.0
                continue
            if voice_seen and rms < silence_threshold:
                silence_after_voice += len(samples) / sample_rate
                if silence_after_voice >= end_silence_seconds:
                    stopped_by_silence = True
                    break
            elif voice_seen:
                silence_after_voice = 0.0
    finally:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
    data = b"".join(chunks)
    duration = len(data) / max(1, sample_rate * 2)
    if stopped_by_silence:
        print(
            f"End-of-turn detectado en vivo: {duration:.2f}s "
            f"(silencio >= {end_silence_seconds:.1f}s)",
            flush=True,
        )
    else:
        print(f"Captura llegó al máximo: {duration:.2f}s", flush=True)
    return data, sample_rate, 1


def _trim_after_end_of_turn_pcm16(
    data: bytes,
    *,
    sample_rate: int,
    end_silence_seconds: float = _DEFAULT_END_SILENCE_SECONDS,
    threshold: int = _DEFAULT_VAD_THRESHOLD,
    frame_ms: int = _DEFAULT_VAD_FRAME_MS,
) -> bytes:
    """Trim audio after the user's full turn.

    Whisper returns only final transcripts in this app, so the remaining risk is
    answering before the user has really stopped. We keep audio through the last
    speech frame plus the configured silence tail (default 1.5s) and never cut
    inside speech. If no speech is detected, return the original buffer so STT
    can decide whether it is empty/noisy.
    """
    if not data or sample_rate <= 0 or end_silence_seconds <= 0 or frame_ms <= 0:
        return data
    sample_count = len(data) // 2
    if sample_count == 0:
        return data
    samples = struct.unpack("<" + "h" * sample_count, data)
    frame_samples = max(1, int(sample_rate * frame_ms / 1000))
    last_voice_sample: int | None = None
    for start in range(0, sample_count, frame_samples):
        frame = samples[start : start + frame_samples]
        if not frame:
            continue
        rms = math.sqrt(sum(sample * sample for sample in frame) / len(frame))
        if rms >= threshold:
            last_voice_sample = min(sample_count, start + len(frame))
    if last_voice_sample is None:
        return data
    silence_tail_samples = int(sample_rate * end_silence_seconds)
    keep_samples = min(sample_count, last_voice_sample + silence_tail_samples)
    return data[: keep_samples * 2]


def _normalize_pcm16(data: bytes, *, target_peak: int) -> bytes:
    samples = struct.unpack("<" + "h" * (len(data) // 2), data) if data else []
    peak = max((abs(sample) for sample in samples), default=0)
    if peak == 0 or peak <= target_peak:
        return data
    scale = target_peak / peak
    normalized = [max(-32768, min(32767, int(sample * scale))) for sample in samples]
    return struct.pack("<" + "h" * len(normalized), *normalized)


if __name__ == "__main__":
    raise SystemExit(main())
