"""Guided Rako product demo without needing the physical button.

Shows OLED states, cue sounds, and speaks a short scripted interaction. Useful
for demos after boot: `rako-demo`.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from bootstrap import build_pi_application
from config import Settings
from hardware.oled_runtime import OledEyeController
from hardware.oled_states import RakoVisualState


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a guided Rako demo")
    parser.add_argument("--audio-device", default="hw:2,0")
    parser.add_argument("--no-playback", action="store_true")
    parser.add_argument("--no-cues", action="store_true")
    parser.add_argument("--no-oled", action="store_true")
    parser.add_argument("--cue-volume", type=float, default=0.14)
    parser.add_argument("--playback-warmup-seconds", type=float, default=0.55)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    eyes = OledEyeController(enabled=not args.no_oled, project_root=project_root)
    play_cue, synthesize_and_maybe_play = _button_tools()
    app = build_pi_application(Settings())
    try:
        print("Rako demo: starting")
        eyes.set_state(RakoVisualState.STARTING)
        time.sleep(0.8)

        eyes.set_state(RakoVisualState.READY)
        play_cue(kind="listen_start", args=args)
        time.sleep(0.35)

        eyes.set_state(RakoVisualState.LISTENING)
        print("Demo user: Rako, hazme un pomodoro de diez minutos para estudiar cálculo.")
        time.sleep(1.0)

        eyes.set_state(RakoVisualState.CAPTURED)
        play_cue(kind="listen_end", args=args)
        time.sleep(0.35)

        eyes.set_state(RakoVisualState.THINKING)
        time.sleep(0.9)

        eyes.set_state(RakoVisualState.FOCUS_RUNNING)
        text = (
            "Listo. Inicié un bloque de foco de diez minutos para estudiar cálculo. "
            "Abre lo necesario, deja el celular lejos, y partamos solo con cinco minutos."
        )
        print(f"Rako demo: {text}")
        synthesize_and_maybe_play(app=app, text=text, eyes=eyes, args=args)

        eyes.set_state(RakoVisualState.FOCUS_DONE)
        time.sleep(1.2)
        eyes.set_state(RakoVisualState.READY)
        print("Rako demo: done")
        return 0
    finally:
        eyes.close()
        app.close()


def _button_tools():
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from button_conversation import _play_cue, _synthesize_and_maybe_play

    return _play_cue, _synthesize_and_maybe_play


if __name__ == "__main__":
    raise SystemExit(main())
