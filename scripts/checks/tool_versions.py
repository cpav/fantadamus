"""Fail when an installed tool's version differs from its pin in tool-versions.toml (R1.9)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from scripts.checks._common import CheckResult, Runner, report, run_command
from scripts.tools.install import BIN, Tool, load_tools

__all__ = ["Runner", "check"]

_VERSION = re.compile(r"(\d+\.\d+\.\d+)")


def check(tools: Iterable[Tool], bin_dir: Path, run: Runner = run_command) -> CheckResult:
    """Run each tool's version command and compare the first x.y.z in its output with the pin."""
    problems: list[str] = []
    for tool in tools:
        executable = bin_dir / tool.binary
        if not executable.exists():
            problems.append(f"{tool.name}: not installed; run `make setup`")
            continue
        completed = run([str(executable), *tool.version_args])
        found = _VERSION.search(completed.stdout + completed.stderr)
        version = found.group(1) if found else "unknown"
        if version != tool.version:
            problems.append(f"{tool.name}: expected {tool.version}, found {version}")
    if problems:
        return CheckResult("tool-versions", ok=False, message="; ".join(problems))
    return CheckResult("tool-versions", ok=True)


if __name__ == "__main__":
    raise SystemExit(report(check(load_tools(), BIN)))
