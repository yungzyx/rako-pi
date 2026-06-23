"""Rako hardware/config smoke checker.

Run this before demos or after reboots to catch the common product blockers:
missing commands, wrong STT/TTS config, ReSpeaker capture, OLED, and playback.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from config import Settings
from db.database import Database
from product.factory_acceptance import build_factory_acceptance_checklist

SCRIPT_DIR = Path(__file__).resolve().parent
BOOT_CONFIG_PATHS = (Path("/boot/firmware/config.txt"), Path("/boot/config.txt"))

Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: Status
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Rako Pi readiness")
    parser.add_argument("--full", action="store_true", help="Run OLED, record, and sound checks")
    parser.add_argument(
        "--calibrate", action="store_true", help="Apply the ReSpeaker capture profile first"
    )
    parser.add_argument("--oled", action="store_true", help="Flash OLED eyes briefly")
    parser.add_argument(
        "--record", action="store_true", help="Record 2s from ReSpeaker and report levels"
    )
    parser.add_argument("--sound", action="store_true", help="Play Rako cue sounds on audio output")
    parser.add_argument("--audio-device", default="plughw:seeed2micvoicec,0")
    parser.add_argument("--capture-device", default="plughw:seeed2micvoicec,0")
    parser.add_argument(
        "--factory",
        action="store_true",
        help="Show product handoff checklist for this configured board",
    )
    args = parser.parse_args()

    if args.full:
        args.oled = True
        args.record = True
        args.sound = True

    settings = Settings()
    results = []
    if args.calibrate:
        results.append(_check_calibrate())
    results.extend(
        [
            _check_python(),
            _check_file(Path(".env"), "env file"),
            _check_command("arecord"),
            _check_command("aplay"),
            _check_command("mpg123"),
            _check_command("gpiomon"),
            _check_boot_audio_overlay(),
            _check_alsa_capture_card(),
            _check_stt(settings),
            _check_tts(settings),
            _check_database_parent(settings),
        ]
    )
    if args.oled:
        results.append(_check_oled())
    if args.record:
        results.append(_check_record(args.capture_device))
    if args.sound:
        results.append(_check_sound(args.audio_device))

    for result in results:
        icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}[result.status]
        print(f"{icon} {result.name}: {result.detail}")

    if args.factory:
        _print_factory_checklist(settings)
    failed = [result for result in results if result.status == "fail"]
    if failed:
        print("\nRako doctor found blockers.")
        return 1
    print("\nRako doctor: listo para probar.")
    return 0


def _check_python() -> CheckResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return CheckResult("python", "ok", f"Python {version}")


def _check_file(path: Path, name: str) -> CheckResult:
    if path.exists():
        return CheckResult(name, "ok", str(path))
    return CheckResult(name, "warn", f"no existe {path}; se usarán defaults/env shell")


def _check_command(command: str) -> CheckResult:
    path = shutil.which(command)
    if path is None:
        return CheckResult(command, "fail", "no está instalado o no está en PATH")
    return CheckResult(command, "ok", path)


def _check_calibrate() -> CheckResult:
    script = Path("scripts/setup_respeaker_audio.sh")
    if not script.exists():
        return CheckResult(
            "audio calibration", "warn", "no existe scripts/setup_respeaker_audio.sh"
        )
    code = subprocess.run(
        [str(script)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
    )
    if code.returncode == 0:
        return CheckResult("audio calibration", "ok", "perfil ReSpeaker aplicado")
    return CheckResult(
        "audio calibration", "warn", code.stdout.strip() or f"exit {code.returncode}"
    )


def _check_boot_audio_overlay(
    config_paths: tuple[Path, ...] = BOOT_CONFIG_PATHS,
) -> CheckResult:
    config = next((path for path in config_paths if path.exists()), None)
    if config is None:
        return CheckResult("ReSpeaker boot overlay", "warn", "no encontré config.txt")
    lines = [
        line.strip()
        for line in config.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    has_voicecard = "dtoverlay=seeed-2mic-voicecard" in lines
    has_i2s = "dtparam=i2s=on" in lines
    if has_voicecard and has_i2s:
        return CheckResult("ReSpeaker boot overlay", "ok", str(config))
    missing = []
    if not has_voicecard:
        missing.append("dtoverlay=seeed-2mic-voicecard")
    if not has_i2s:
        missing.append("dtparam=i2s=on")
    return CheckResult(
        "ReSpeaker boot overlay",
        "fail",
        "falta " + ", ".join(missing) + "; ejecuta sudo ./scripts/rako-fix-audio-boot y reinicia",
    )


def _check_alsa_capture_card() -> CheckResult:
    if shutil.which("arecord") is None:
        return CheckResult("ReSpeaker ALSA", "fail", "arecord no disponible")
    output = _run_text(["arecord", "-L"])
    if "seeed2micvoicec" in output:
        return CheckResult("ReSpeaker ALSA", "ok", "capture card seeed2micvoicec visible")
    return CheckResult("ReSpeaker ALSA", "warn", "no veo seeed2micvoicec en arecord -L")


def _check_stt(settings: Settings) -> CheckResult:
    if settings.stt_provider == "openai_whisper":
        if not settings.openai_api_key:
            return CheckResult(
                "STT", "fail", "openai_whisper seleccionado pero falta OPENAI_API_KEY"
            )
        if importlib.util.find_spec("openai") is None:
            return CheckResult("STT", "fail", "falta paquete openai")
        return CheckResult("STT", "ok", f"OpenAI Whisper ({settings.openai_stt_model})")
    if settings.stt_provider == "google":
        if not settings.google_application_credentials:
            return CheckResult("STT", "warn", "Google STT sin GOOGLE_APPLICATION_CREDENTIALS")
        return CheckResult("STT", "ok", f"Google STT ({settings.google_stt_language})")
    return CheckResult("STT", "warn", f"proveedor desconocido: {settings.stt_provider}")


def _check_tts(settings: Settings) -> CheckResult:
    if settings.tts_provider == "elevenlabs":
        if not settings.elevenlabs_api_key:
            return CheckResult(
                "TTS", "fail", "ElevenLabs seleccionado pero falta ELEVENLABS_API_KEY"
            )
        return CheckResult("TTS", "ok", f"ElevenLabs voice {settings.elevenlabs_voice_id}")
    if settings.tts_provider == "google":
        if not settings.google_application_credentials:
            return CheckResult("TTS", "warn", "Google TTS sin GOOGLE_APPLICATION_CREDENTIALS")
        return CheckResult("TTS", "ok", f"Google TTS {settings.google_tts_voice}")
    return CheckResult("TTS", "warn", f"proveedor desconocido: {settings.tts_provider}")


def _check_database_parent(settings: Settings) -> CheckResult:
    path = Path(settings.sqlite_path)
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".rako-doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        return CheckResult("SQLite path", "fail", f"{parent} no escribible: {exc}")
    return CheckResult("SQLite path", "ok", str(path))


def _check_oled() -> CheckResult:
    code = subprocess.run(
        [sys.executable, "eyes.py", "wink", "--seconds", "1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if code.returncode == 0:
        return CheckResult("OLED", "ok", "wink render OK")
    return CheckResult("OLED", "fail", code.stderr.strip() or f"exit {code.returncode}")


def _check_record(device: str) -> CheckResult:
    try:
        metrics = _record_metrics(device=device, sample_rate=16000, seconds=2)
    except Exception as exc:
        return CheckResult("record", "fail", str(exc))
    if metrics["peak"] == 0:
        return CheckResult("record", "fail", "silencio total desde ALSA")
    peak_ratio = metrics["peak"] / 32768
    rms_ratio = metrics["rms"] / 32768
    advice = "nivel sano"
    status: Status = "ok"
    if peak_ratio > 0.92:
        status = "warn"
        advice = "muy cerca de clipping; baja ganancia o habla más lejos"
    elif rms_ratio < 0.015:
        status = "warn"
        advice = "señal baja; habla más cerca o sube ganancia"
    return CheckResult(
        "record",
        status,
        (
            f"{metrics['bytes']} bytes desde {device}; "
            f"rms={metrics['rms']:.0f} ({rms_ratio:.1%}), "
            f"peak={metrics['peak']} ({peak_ratio:.1%}) — {advice}"
        ),
    )


def _check_sound(device: str) -> CheckResult:
    try:
        ns = argparse.Namespace(
            no_playback=False,
            no_cues=False,
            audio_device=device,
            cue_volume=0.18,
        )
        _, play_cue = _button_tools()
        play_cue(kind="listen_start", args=ns)
        play_cue(kind="listen_end", args=ns)
        play_cue(kind="reply_start", args=ns)
    except Exception as exc:
        return CheckResult("sound", "fail", str(exc))
    return CheckResult("sound", "ok", f"cues enviados a {device}")


def _record_metrics(*, device: str, sample_rate: int, seconds: int) -> dict[str, float | int]:
    if shutil.which("arecord") is None:
        raise RuntimeError("arecord is not installed")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        subprocess.run(
            [
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
                str(seconds),
                tmp.name,
            ],
            check=True,
        )
        with wave.open(tmp.name, "rb") as wav:
            data = wav.readframes(wav.getnframes())
    samples = struct.unpack("<" + "h" * (len(data) // 2), data) if data else []
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) if samples else 0
    peak = max((abs(sample) for sample in samples), default=0)
    return {"bytes": len(data), "rms": rms, "peak": peak}


def _button_tools():
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from button_conversation import _capture_with_arecord, _play_cue

    return _capture_with_arecord, _play_cue


def _run_text(command: list[str]) -> str:
    completed = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
    )
    return completed.stdout


def _print_factory_checklist(settings: Settings) -> None:
    print("\nFactory acceptance checklist:")
    db = Database.open(settings.sqlite_path, key=settings.sqlite_encryption_key)
    try:
        checklist = build_factory_acceptance_checklist(db, settings)
    finally:
        db.close()
    for item in checklist.items:
        icon = {"ok": "✅", "warn": "⚠️", "fail": "❌", "manual": "☐"}[item.status]
        print(f"{icon} [{item.category}] {item.name}: {item.detail}")
    print(
        "\nFactory summary: "
        f"ready_for_handoff={checklist.ready_for_handoff}, "
        f"failures={checklist.automatic_failures}, "
        f"warnings={checklist.automatic_warnings}, "
        f"manual_items={checklist.manual_items}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
