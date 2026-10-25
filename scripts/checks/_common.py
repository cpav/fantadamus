"""Shared result type and entry point for the checks in `make check`."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    stdin_text: str | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and capture its output; the default runner for checks and hooks.

    With a timeout, the command runs in its own process group and the whole group is killed when time runs
    out: killing only the command would leave its children holding the output pipes open, and the wait
    would never end. The `TimeoutExpired` raised then carries the output produced so far.
    """
    stdin = subprocess.PIPE if stdin_text is not None else None
    with subprocess.Popen(  # noqa: S603  # reason: fixed argument lists built by the checks, never shell strings
        list(args), stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, env=env,
        start_new_session=timeout is not None,
    ) as process:  # fmt: skip
        try:
            stdout, stderr = process.communicate(stdin_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(list(args), timeout or 0, output=stdout, stderr=stderr) from None
    return subprocess.CompletedProcess(list(args), process.returncode, stdout, stderr)


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one check: its name, whether it passed, and a one-line message."""

    name: str
    ok: bool
    message: str = ""


def report(result: CheckResult) -> int:
    """Print the one-line summary `make check` collects and return the process exit code."""
    status = "PASS" if result.ok else "FAIL"
    line = f"{status} {result.name}" + (f": {result.message}" if result.message else "")
    print(line, file=sys.stdout if result.ok else sys.stderr)
    return 0 if result.ok else 1
