"""Fail when a change weakens a gate threshold relative to the base branch (R6.5, R8.4).

The base is $FANTADAMUS_BASE_REF if set, else origin/main if it exists, else main.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from collections.abc import Mapping
from pathlib import Path

from scripts.checks._common import CheckResult, report

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = "config/thresholds.toml"

Thresholds = Mapping[str, Mapping[str, object]]


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"threshold value must be a number, got {value!r}")
    return float(value)


def _show(value: object) -> str:
    return str(value)


def compare(old: Thresholds, new: Thresholds) -> list[str]:
    """List every threshold the new file weakens, removes or turns around."""
    issues: list[str] = []
    for name, before in old.items():
        after = new.get(name)
        if after is None:
            issues.append(f"{name} removed")
            continue
        if after.get("direction") != before.get("direction"):
            was, now = before.get("direction"), after.get("direction")
            issues.append(f"{name} direction changed: {was} → {now}")
            continue
        old_value, new_value = _number(before["value"]), _number(after["value"])
        direction = before["direction"]
        if (direction == "up" and new_value < old_value) or (direction == "down" and new_value > old_value):
            change = f"{_show(before['value'])} → {_show(after['value'])}"
            issues.append(f"{name} weakened: {change} (may only go {direction})")
    return issues


def load_current(root: Path = ROOT) -> dict[str, dict[str, object]]:
    return tomllib.loads((root / RELATIVE).read_text(encoding="utf-8"))


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603  # reason: fixed git subcommands with a ref chosen by this script
        ["git", *args],  # noqa: S607  # reason: git from PATH, as in every developer shell and CI runner
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def base_ref() -> str:
    explicit = os.environ.get("FANTADAMUS_BASE_REF")
    if explicit:
        return explicit
    has_origin = _git("rev-parse", "--verify", "--quiet", "origin/main").returncode == 0
    return "origin/main" if has_origin else "main"


def load_base(ref: str) -> dict[str, dict[str, object]] | None:
    shown = _git("show", f"{ref}:{RELATIVE}")
    return tomllib.loads(shown.stdout) if shown.returncode == 0 else None


def check() -> CheckResult:
    ref = base_ref()
    base = load_base(ref)
    if base is None:
        return CheckResult("thresholds", ok=True, message=f"no {RELATIVE} on {ref} yet")
    issues = compare(base, load_current())
    if issues:
        return CheckResult("thresholds", ok=False, message=f"against {ref}: " + "; ".join(issues))
    return CheckResult("thresholds", ok=True)


if __name__ == "__main__":
    raise SystemExit(report(check()))
