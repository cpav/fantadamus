"""Every budget timed once for the whole test run (mvp-store design C7; R5.2). `python -m tests.lineup_speed
--all` starts in the background as soon as a run has a budget test, and the run puts its budget tests last, so
that by the time they come its result is there. It runs outside any one test, so a busy machine slows it down
without breaking a test's two-minute limit. Whatever it ends with, a result or a failure, is written once in a
folder every worker shares, and read by every budget test from there."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scripts.checks._common import run_command

from fantadamus.core.files import temporary_beside

ROOT = Path(__file__).resolve().parents[1]
STARTED, RESULT, FAILED = "started", "timings.json", "failed.txt"
SECONDS = 900
"""The most it may take, from the moment it started: about a minute alone, three on the busiest Mac seen."""
POLL = 0.25


def command() -> list[str]:
    return [sys.executable, "-m", "tests.lineup_speed", "--all"]


def _write(path: Path, text: str) -> None:
    temporary = temporary_beside(path)
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _run(folder: Path, args: Sequence[str]) -> None:
    try:
        run = run_command(args, cwd=ROOT, timeout=SECONDS)
    except subprocess.TimeoutExpired:
        _write(folder / FAILED, f"the timing process took more than {SECONDS} seconds")
        return
    if run.returncode != 0:
        _write(folder / FAILED, run.stderr or f"the timing process ended with {run.returncode}")
    else:
        _write(folder / RESULT, run.stdout)


def begin(folder: Path, args: Sequence[str]) -> bool:
    """Start `args` in the background unless this run already has: the first worker to make the marker does.
    Returns whether this call started it."""
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.close(os.open(folder / STARTED, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    threading.Thread(target=_run, args=(folder, list(args)), daemon=True).start()
    return True


def measured(folder: Path, args: Sequence[str]) -> dict[str, Any]:
    """What the timing process printed: started now if nothing has started it, and waited for if it's still
    running. Its failure, if it failed, for every test that asks."""
    begin(folder, args)
    deadline = (folder / STARTED).stat().st_mtime + SECONDS + 30
    while not (folder / RESULT).is_file():
        if (folder / FAILED).is_file():
            raise RuntimeError((folder / FAILED).read_text(encoding="utf-8"))
        if time.time() > deadline:
            raise TimeoutError(f"no timing came in {SECONDS} seconds")
        time.sleep(POLL)
    found: dict[str, Any] = json.loads((folder / RESULT).read_text(encoding="utf-8"))
    return found
