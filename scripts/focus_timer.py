"""Run a Rako focus countdown from the terminal.

This is a practical runtime bridge until the main Rako service owns timers.
It can drive OLED expressions by launching `eyes.py` in loop mode.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from db.database import Database
from db.types import TaskStatus
from productivity.countdown import CountdownConfig, CountdownRunner
from productivity.focus import FocusSession, create_focus_task, start_focus_session


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a Rako focus countdown")
    parser.add_argument("title", help="Task title")
    parser.add_argument("--minutes", type=int, default=25)
    parser.add_argument(
        "--seconds", type=int, default=None, help="Override duration for quick tests"
    )
    parser.add_argument("--db", default="data/rako.db")
    parser.add_argument("--oled", action="store_true", help="Show OLED eyes while timer runs")
    parser.add_argument("--tick-seconds", type=float, default=60.0)
    args = parser.parse_args()

    now = datetime.now(UTC)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    db = Database.open(args.db)
    eyes = None
    try:
        task = db.tasks.create(create_focus_task(args.title, now))
        session = start_focus_session(task, now, minutes=args.minutes)
        if args.seconds is not None:
            session = FocusSession(
                id=session.id,
                task_id=session.task_id,
                task_title=session.task_title,
                started_at=session.started_at,
                duration=timedelta(seconds=args.seconds),
                status=session.status,
            )
        print(
            f"Rako focus started: {session.task_title} ({_format_duration(session.duration)})",
            flush=True,
        )
        if args.oled:
            eyes = _start_eyes("neutral")
        runner = CountdownRunner(config=CountdownConfig(tick_seconds=args.tick_seconds))
        completed = runner.run(session, on_tick=_print_tick, on_done=_print_done)
        db.tasks.update_status(
            completed.task_id, status=TaskStatus.DONE, completed_at=completed.ends_at
        )
        if eyes is not None:
            _stop_process(eyes)
            _start_eyes_once("happy", seconds=3)
        return 0
    except KeyboardInterrupt:
        print("\nFocus cancelled.", flush=True)
        if eyes is not None:
            _stop_process(eyes)
        return 130
    finally:
        db.close()


def _format_duration(duration: timedelta) -> str:
    total = int(duration.total_seconds())
    minutes, seconds = divmod(total, 60)
    return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"


def _print_tick(remaining: timedelta) -> None:
    total = int(remaining.total_seconds())
    minutes, seconds = divmod(total, 60)
    print(f"Remaining: {minutes:02d}:{seconds:02d}", flush=True)


def _print_done(_) -> None:
    print("Focus complete. Buen trabajo: pausa breve o seguimos con otro bloque.", flush=True)


def _start_eyes(expression: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "eyes.py", expression, "--loop"])


def _start_eyes_once(expression: str, *, seconds: int) -> None:
    subprocess.run([sys.executable, "eyes.py", expression, "--seconds", str(seconds)], check=False)


def _stop_process(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
