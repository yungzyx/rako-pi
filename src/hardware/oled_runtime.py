"""Runtime controller for Rako OLED eyes.

The renderer still lives in the top-level `eyes.py` script. This controller owns
one renderer subprocess at a time so callers can switch expressions without
multiple processes fighting over the I2C OLED.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hardware.oled_states import RakoVisualState, expression_for_state


class ProcessLike(Protocol):
    def terminate(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def kill(self) -> None: ...


class PopenFactory(Protocol):
    def __call__(self, args: list[str], **kwargs: object) -> ProcessLike: ...


@dataclass(slots=True)
class OledEyeController:
    enabled: bool = True
    project_root: Path = Path(".")
    python: str = sys.executable
    popen: PopenFactory = subprocess.Popen
    _process: ProcessLike | None = None
    _expression: str | None = None

    def set_state(self, state: RakoVisualState) -> None:
        self.set_expression(expression_for_state(state))

    def set_expression(self, expression: str) -> None:
        if not self.enabled:
            return
        if expression == self._expression:
            return
        self.stop()
        self._process = self.popen(
            [self.python, "eyes.py", expression, "--loop"],
            cwd=str(self.project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._expression = expression

    def flash_state(self, state: RakoVisualState, *, seconds: float = 1.2) -> None:
        self.flash_expression(expression_for_state(state), seconds=seconds)

    def flash_expression(self, expression: str, *, seconds: float = 1.2) -> None:
        if not self.enabled:
            return
        subprocess.run(
            [self.python, "eyes.py", expression, "--seconds", str(seconds)],
            cwd=str(self.project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def stop(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=2)
        finally:
            self._process = None
            self._expression = None

    def close(self) -> None:
        self.stop()
