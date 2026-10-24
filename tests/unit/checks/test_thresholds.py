"""Task 4.3: a gate threshold may only move in its safe direction (R6.5, R8.4)."""

from __future__ import annotations

from scripts.checks import thresholds

BASE = {
    "coverage_line": {"value": 90, "direction": "up"},
    "coverage_branch": {"value": 90, "direction": "up"},
    "ci_time_budget_minutes": {"value": 5, "direction": "down"},
}


def _with(name: str, value: float) -> dict[str, dict[str, object]]:
    changed = {key: dict(entry) for key, entry in BASE.items()}
    changed[name]["value"] = value
    return changed


def test_weakened_coverage_fails() -> None:
    issues = thresholds.compare(BASE, _with("coverage_line", 85))
    assert issues == ["coverage_line weakened: 90 → 85 (may only go up)"]


def test_raised_time_budget_fails() -> None:
    issues = thresholds.compare(BASE, _with("ci_time_budget_minutes", 8))
    assert issues == ["ci_time_budget_minutes weakened: 5 → 8 (may only go down)"]


def test_strengthening_passes() -> None:
    assert thresholds.compare(BASE, _with("coverage_branch", 92)) == []
    assert thresholds.compare(BASE, _with("ci_time_budget_minutes", 4)) == []


def test_removed_or_redirected_threshold_fails() -> None:
    removed = {key: entry for key, entry in BASE.items() if key != "coverage_branch"}
    assert thresholds.compare(BASE, removed) == ["coverage_branch removed"]
    flipped = {key: dict(entry) for key, entry in BASE.items()}
    flipped["coverage_line"]["direction"] = "down"
    assert thresholds.compare(BASE, flipped) == ["coverage_line direction changed: up → down"]


def test_repository_file_declares_required_thresholds() -> None:
    current = thresholds.load_current()
    assert thresholds.compare({"coverage_line": {"value": 90, "direction": "up"}}, current) == []
    assert thresholds.compare({"coverage_branch": {"value": 90, "direction": "up"}}, current) == []
    assert current["ci_time_budget_minutes"]["direction"] == "down"
