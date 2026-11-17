"""Every budget timed once for the whole test run (mvp-store design C7; R5.2): the first test to ask runs
`python -m tests.lineup_speed --all`, behind a file lock, and every other test, in this worker or another,
reads what it printed."""

from __future__ import annotations

import fcntl
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.checks._common import run_command

ROOT = Path(__file__).resolve().parents[1]
SECONDS = 115
"""Long enough for the process inside a busy suite: it takes about a minute alone."""


def measured() -> dict[str, Any]:
    """The timing process's result: every budget's CPU seconds."""
    timed = run_command([sys.executable, "-m", "tests.lineup_speed", "--all"], cwd=ROOT, timeout=SECONDS)
    if timed.returncode != 0:
        raise RuntimeError(f"the timing process failed:\n{timed.stderr}")
    found: dict[str, Any] = json.loads(timed.stdout)
    return found


def shared(path: Path, measure: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """`measure`'s result, kept in `path`: measured by whoever comes first, holding the lock beside it, and
    read by the rest."""
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not path.is_file():
            path.write_text(json.dumps(measure()), encoding="utf-8")
    found: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return found
