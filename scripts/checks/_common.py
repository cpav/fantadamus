"""Shared result type and entry point for the checks in `make check`."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a command and capture its output; the default runner for checks."""
    return subprocess.run(list(args), capture_output=True, text=True, check=False)  # noqa: S603  # reason: fixed argument lists built by the checks, never shell strings


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
