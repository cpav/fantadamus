"""Task 5.3: line and branch coverage are gated separately against their thresholds (R8.1 to R8.3)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.checks import coverage_gate


def _totals(lines: tuple[int, int], branches: tuple[int, int]) -> dict[str, int]:
    return {
        "covered_lines": lines[0],
        "num_statements": lines[1],
        "covered_branches": branches[0],
        "num_branches": branches[1],
    }


def test_branch_below_threshold_fails() -> None:
    result = coverage_gate.evaluate(_totals((95, 100), (80, 100)), line_min=90, branch_min=90)
    assert not result.ok
    assert result.message == "branch coverage 80.0% < 90%"


def test_line_below_threshold_fails() -> None:
    result = coverage_gate.evaluate(_totals((89, 100), (100, 100)), line_min=90, branch_min=90)
    assert not result.ok
    assert result.message == "line coverage 89.0% < 90%"


def test_both_at_or_above_threshold_pass() -> None:
    result = coverage_gate.evaluate(_totals((90, 100), (45, 50)), line_min=90, branch_min=90)
    assert result.ok
    assert result.message == "lines 90.0%, branches 90.0%"


def test_no_branches_counts_as_full_branch_coverage() -> None:
    assert coverage_gate.evaluate(_totals((10, 10), (0, 0)), line_min=90, branch_min=90).ok


def test_reads_totals_from_coverage_json(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"totals": _totals((9, 10), (1, 2))}), encoding="utf-8")
    assert coverage_gate.read_totals(report) == _totals((9, 10), (1, 2))


def test_missing_report_fails(tmp_path: Path) -> None:
    result = coverage_gate.check(tmp_path / "coverage.json")
    assert not result.ok
    assert "not found" in result.message


def test_check_uses_repository_thresholds(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"totals": _totals((50, 100), (100, 100))}), encoding="utf-8")
    result = coverage_gate.check(report)
    assert not result.ok
    assert result.message.startswith("line coverage 50.0% < ")
