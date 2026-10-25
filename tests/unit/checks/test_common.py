"""The shared check runner and summary line."""

from __future__ import annotations

import sys

import pytest
from scripts.checks._common import CheckResult, report, run_command


def test_run_command_captures_output() -> None:
    completed = run_command([sys.executable, "-c", "print('hello')"])
    assert completed.returncode == 0
    assert completed.stdout.strip() == "hello"


def test_report_pass_and_fail(capsys: pytest.CaptureFixture[str]) -> None:
    assert report(CheckResult("demo", ok=True)) == 0
    assert report(CheckResult("demo", ok=False, message="broken")) == 1
    captured = capsys.readouterr()
    assert captured.out == "PASS demo\n"
    assert captured.err == "FAIL demo: broken\n"
