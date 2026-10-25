"""Fail when line or branch coverage of src/ and scripts/ is below its threshold (R8.1 to R8.3).

Reads coverage.json (written by `pytest --cov --cov-report=json`) and config/thresholds.toml.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from scripts.checks import thresholds
from scripts.checks._common import CheckResult, report

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "coverage.json"


def _percent(covered: int, total: int) -> float:
    return 100.0 if total == 0 else 100.0 * covered / total


def evaluate(totals: Mapping[str, int], line_min: float, branch_min: float) -> CheckResult:
    """Compare line and branch coverage with their minimums, separately."""
    line = _percent(totals["covered_lines"], totals["num_statements"])
    branch = _percent(totals["covered_branches"], totals["num_branches"])
    failures = []
    if line < line_min:
        failures.append(f"line coverage {line:.1f}% < {line_min:g}%")
    if branch < branch_min:
        failures.append(f"branch coverage {branch:.1f}% < {branch_min:g}%")
    if failures:
        return CheckResult("coverage", ok=False, message="; ".join(failures))
    return CheckResult("coverage", ok=True, message=f"lines {line:.1f}%, branches {branch:.1f}%")


def read_totals(path: Path = REPORT) -> dict[str, int]:
    totals = json.loads(path.read_text(encoding="utf-8"))["totals"]
    keys = ("covered_lines", "num_statements", "covered_branches", "num_branches")
    return {key: int(totals[key]) for key in keys}


def _minimum(name: str) -> float:
    value = thresholds.load_current()[name]["value"]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be a number, got {value!r}")
    return float(value)


def check(path: Path = REPORT) -> CheckResult:
    if not path.exists():
        missing = f"{path.name} not found; run the tests with coverage first"
        return CheckResult("coverage", ok=False, message=missing)
    return evaluate(read_totals(path), _minimum("coverage_line"), _minimum("coverage_branch"))


if __name__ == "__main__":
    raise SystemExit(report(check()))
