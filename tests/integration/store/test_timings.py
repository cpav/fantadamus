"""mvp-store task 5.2: one process times every budget for a whole run, started in the background as the
run begins; each test reads its own number, and a failure is read by every test at once (design C7; R5.1,
R5.2)."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tests import timings

STARTS = """
import json, pathlib, sys, time
runs = pathlib.Path(sys.argv[1])
runs.write_text(runs.read_text() + "run\\n" if runs.exists() else "run\\n")
time.sleep(0.3)
if sys.argv[2] == "fail":
    sys.exit("the round couldn't be built")
print(json.dumps({"lineup": 0.5, "season": {"store": 0.4}}))
"""
"""A stand-in for the timing process: it counts its runs, and succeeds or fails as told."""


def _asked(folder: Path, runs: Path, outcome: str) -> list[Any]:
    """Four tests asking at once, as four workers do."""

    def ask(_: int) -> Any:
        try:
            return timings.measured(folder, [sys.executable, "-c", STARTS, str(runs), outcome])
        except RuntimeError as error:
            return str(error)

    with ThreadPoolExecutor(4) as pool:
        return list(pool.map(ask, range(4)))


def test_one_process_for_a_whole_run(tmp_path: Path) -> None:
    runs = tmp_path / "runs.txt"
    assert _asked(tmp_path / "timings", runs, "succeed") == [{"lineup": 0.5, "season": {"store": 0.4}}] * 4
    assert runs.read_text().splitlines() == ["run"]  # once, whoever asked first
    assert _asked(tmp_path / "timings", runs, "succeed")[0]["lineup"] == 0.5  # later, from its file alone
    assert runs.read_text().splitlines() == ["run"]


def test_a_failure_is_read_by_every_test_at_once(tmp_path: Path) -> None:
    """Not run again by each in turn: one failure, read by all."""
    runs = tmp_path / "runs.txt"
    assert _asked(tmp_path / "timings", runs, "fail") == ["the round couldn't be built\n"] * 4
    assert runs.read_text().splitlines() == ["run"]


def test_begun_before_it_is_asked_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The run starts it as it begins; the test that asks later only reads it."""
    runs, folder = tmp_path / "runs.txt", tmp_path / "timings"
    args = [sys.executable, "-c", STARTS, str(runs), "succeed"]
    assert timings.begin(folder, args)
    assert not timings.begin(folder, args)  # one start a run
    assert timings.measured(folder, args)["lineup"] == 0.5
    assert runs.read_text().splitlines() == ["run"]
