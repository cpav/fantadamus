"""Task 9.3: at the end of a turn, run `make check` when anything changed (R17.3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts.hooks import stop_check
from scripts.hooks.event import HookEvent

RED = (
    "==> lint\nE501 Line too long\nPASS format\nFAIL lint: ruff found 1 problem\nPASS types\n"
    "17 passed, 1 failed\n"
)


def _stop(active: bool = False) -> HookEvent:
    return HookEvent(hook_event_name="Stop", stop_hook_active=active)


def _check(code: int, output: str = "") -> stop_check.CheckRunner:
    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["make", "check"], code, stdout=output, stderr="")

    return run


def _never() -> subprocess.CompletedProcess[str]:
    raise AssertionError("make check must not run")


def test_no_changes_reports_no_check(tmp_path: Path) -> None:
    last_green = tmp_path / "last-green"
    last_green.write_text("abc\n", encoding="utf-8")
    result = stop_check.handle(_stop(), state="abc", last_green=last_green, run_check=_never)
    assert result.code == 0
    assert "no check needed" in result.stdout


def test_green_records_the_state(tmp_path: Path) -> None:
    last_green = tmp_path / "last-green"
    result = stop_check.handle(
        _stop(), state="abc", last_green=last_green, run_check=_check(0, "18 passed\n")
    )
    assert result.code == 0
    assert "make check passed" in result.stdout
    assert last_green.read_text(encoding="utf-8") == "abc\n"


def test_red_first_time_blocks(tmp_path: Path) -> None:
    last_green = tmp_path / "last-green"
    last_green.write_text("old\n", encoding="utf-8")
    result = stop_check.handle(_stop(), state="new", last_green=last_green, run_check=_check(2, RED))
    assert result.code == 2
    assert "FAIL lint: ruff found 1 problem" in result.stderr
    assert "17 passed, 1 failed" in result.stderr
    assert "PASS format" not in result.stderr
    assert last_green.read_text(encoding="utf-8") == "old\n"


def test_red_again_allows_stop_with_message(tmp_path: Path) -> None:
    result = stop_check.handle(
        _stop(active=True), state="new", last_green=tmp_path / "last-green", run_check=_check(2, RED)
    )
    assert result.code == 1  # a non-blocking error: the turn ends and the user sees why
    assert "still red" in result.stderr
    assert "FAIL lint" in result.stderr


def test_timeout_is_failure(tmp_path: Path) -> None:
    def slow() -> subprocess.CompletedProcess[str]:
        partial = "==> lint\nAll checks passed!\n==> audit\n"
        raise subprocess.TimeoutExpired(["make", "check"], stop_check.TIMEOUT_SECONDS, output=partial)

    result = stop_check.handle(_stop(), state="new", last_green=tmp_path / "last-green", run_check=slow)
    assert result.code == 2
    assert "timed out after 10 minutes" in result.stderr
    assert "while running: audit" in result.stderr
    assert not (tmp_path / "last-green").exists()


def test_failing_tests_are_named(tmp_path: Path) -> None:
    output = (
        "==> tests\nFAILED tests/unit/test_a.py::test_b - assert 1 == 2\nFAIL tests\n17 passed, 1 failed\n"
    )
    result = stop_check.handle(_stop(), state="s", last_green=tmp_path / "g", run_check=_check(2, output))
    assert "FAILED tests/unit/test_a.py::test_b" in result.stderr


def test_full_output_is_kept_for_the_owner(tmp_path: Path) -> None:
    log = tmp_path / "stop-check.log"
    stop_check.handle(_stop(), state="s", last_green=tmp_path / "g", run_check=_check(2, RED), log=log)
    assert log.read_text(encoding="utf-8") == RED


@pytest.mark.parametrize("output", ["", "something broke before any check ran\n"])
def test_unparsed_failure_shows_the_tail(tmp_path: Path, output: str) -> None:
    result = stop_check.handle(_stop(), state="s", last_green=tmp_path / "g", run_check=_check(2, output))
    assert result.code == 2
    assert output.strip() in result.stderr
