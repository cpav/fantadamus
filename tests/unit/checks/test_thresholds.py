"""Task 4.3: a gate threshold may only move in its safe direction (R6.5, R8.4)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping

import pytest
from scripts.checks import thresholds
from scripts.checks._common import CheckResult

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


def _fake_git(
    responses: Mapping[tuple[str, ...], tuple[int, str]],
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        code, out = responses.get(args, (1, ""))
        return subprocess.CompletedProcess(["git", *args], code, stdout=out, stderr="")

    return git


def test_base_ref_prefers_explicit_then_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTADAMUS_BASE_REF", "release")
    assert thresholds.base_ref() == "release"
    monkeypatch.delenv("FANTADAMUS_BASE_REF")
    has_origin: dict[tuple[str, ...], tuple[int, str]] = {
        ("rev-parse", "--verify", "--quiet", "origin/main"): (0, "abc\n")
    }
    monkeypatch.setattr(thresholds, "_git", _fake_git(has_origin))
    assert thresholds.base_ref() == "origin/main"
    monkeypatch.setattr(thresholds, "_git", _fake_git({}))
    assert thresholds.base_ref() == "main"


def test_check_against_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTADAMUS_BASE_REF", "main")
    stricter = '[coverage_line]\nvalue = 99\ndirection = "up"\n'
    monkeypatch.setattr(
        thresholds, "_git", _fake_git({("show", "main:config/thresholds.toml"): (0, stricter)})
    )
    result = thresholds.check()
    assert not result.ok
    assert result.message.startswith("against main: coverage_line weakened: 99 → ")
    monkeypatch.setattr(thresholds, "_git", _fake_git({}))
    assert thresholds.check() == CheckResult(
        "thresholds", ok=True, message="no config/thresholds.toml on main yet"
    )


def test_non_numeric_threshold_is_rejected() -> None:
    with pytest.raises(TypeError):
        thresholds.compare({"x": {"value": 1, "direction": "up"}}, {"x": {"value": True, "direction": "up"}})


def test_real_git_reads_this_repository() -> None:
    assert thresholds._git("rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
