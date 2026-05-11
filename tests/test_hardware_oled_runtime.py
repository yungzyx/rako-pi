from __future__ import annotations

from pathlib import Path

from hardware.oled_runtime import OledEyeController
from hardware.oled_states import RakoVisualState


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


def test_eye_controller_starts_expression_loop() -> None:
    calls = []

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return FakeProcess()

    eyes = OledEyeController(project_root=Path("/repo"), python="python", popen=fake_popen)

    eyes.set_state(RakoVisualState.LISTENING)

    assert calls[0][0] == ["python", "eyes.py", "listening", "--loop"]
    assert calls[0][1]["cwd"] == "/repo"


def test_eye_controller_replaces_previous_expression() -> None:
    processes: list[FakeProcess] = []

    def fake_popen(args, **kwargs):
        process = FakeProcess()
        processes.append(process)
        return process

    eyes = OledEyeController(popen=fake_popen)

    eyes.set_state(RakoVisualState.LISTENING)
    eyes.set_state(RakoVisualState.THINKING)

    assert processes[0].terminated is True
    assert len(processes) == 2


def test_eye_controller_ignores_duplicate_expression() -> None:
    calls = []

    def fake_popen(args, **kwargs):
        calls.append(args)
        return FakeProcess()

    eyes = OledEyeController(popen=fake_popen)

    eyes.set_state(RakoVisualState.READY)
    eyes.set_state(RakoVisualState.IDLE)

    assert len(calls) == 1


def test_eye_controller_disabled_does_nothing() -> None:
    calls = []

    def fake_popen(args, **kwargs):
        calls.append(args)
        return FakeProcess()

    eyes = OledEyeController(enabled=False, popen=fake_popen)

    eyes.set_state(RakoVisualState.SPEAKING)

    assert calls == []
