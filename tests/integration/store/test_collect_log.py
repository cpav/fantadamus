"""mvp-store task 4.2: an answer reads the collection log from its window's start, and scoring a round reads
it back to that round (design C6; R1.5, R3.4)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pytest
from pydantic import BaseModel

from fantadamus.core.clock import fixed_clock
from fantadamus.domains.calibration import RoundFrame
from fantadamus.lake import jsonl
from fantadamus.lake.calibration_store import CalibrationStore
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.advisor import Facts
from fantadamus.mcp.calibrate import Calibrator
from fantadamus.web.cadence import may_read, what_is_due
from fantadamus.web.collector import CollectReport, PageReport
from tests.property.collect.test_forecast import READ, _filled
from tests.xy_harness import NOW

URL = "https://example.org/round"


def run(at: dt.datetime, page: str = "round") -> CollectReport:
    return CollectReport(
        started_at=at,
        finished_at=at,
        round=None,
        pages=[
            PageReport(url=URL, page=page, outcome="unchanged", fetched_at=at, confirmed=["outlet_views"])
        ],
    )


@pytest.fixture
def parsed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setattr(jsonl, "_PARSED", {})
    parse = jsonl._parse
    seen: list[str] = []

    def counting(path: Path, model: type[BaseModel]) -> list[BaseModel]:
        seen.append(path.name)
        return parse(path, model)

    monkeypatch.setattr(jsonl, "_parse", counting)
    return seen


def test_only_the_windows_months(tmp_path: Path, parsed: list[str]) -> None:
    store = LakeStore(tmp_path / "lake")
    advisor, _ = _filled(store)
    log = CollectLog(tmp_path / "collect")
    for at in (NOW - dt.timedelta(days=70), NOW - dt.timedelta(days=40), READ):
        log.append(run(at))
    advisor = dataclasses.replace(advisor, collect_log=log)
    advisor.gather([], NOW, facts=Facts.read(store, NOW), known=[])
    assert parsed == [f"{NOW:%Y-%m}.jsonl"]  # the window's month, not the two before


def test_scoring_a_round_reads_back_to_it(tmp_path: Path, parsed: list[str]) -> None:
    """A round scored again weeks later reads the log from that round's window; a recent one from its own."""
    log = CollectLog(tmp_path / "collect")
    for at in (dt.datetime(2026, 8, 25, tzinfo=dt.UTC), dt.datetime(2026, 9, 16, tzinfo=dt.UTC), READ):
        log.append(run(at, page="statistics"))
    calibrator = Calibrator(
        lake=LakeStore(tmp_path / "lake"),
        log=DecisionLog(tmp_path / "decisions"),
        store=CalibrationStore(tmp_path / "calibration"),
        clock=fixed_clock(NOW),
        collect_log=log,
    )

    def frame(first: dt.datetime) -> RoundFrame:
        return RoundFrame(round=3, matches=[], first_kickoff=first, last_kickoff=first, next_kickoff=None)

    calibrator.bracketing_reads(frame(dt.datetime(2026, 9, 5, tzinfo=dt.UTC)), NOW, read=False)
    assert parsed == ["2026-08.jsonl", "2026-09.jsonl", "2026-10.jsonl"]
    jsonl._PARSED.clear()
    parsed.clear()
    calibrator.bracketing_reads(frame(dt.datetime(2026, 10, 24, tzinfo=dt.UTC)), NOW, read=False)
    assert parsed == ["2026-10.jsonl"]
    assert log.worked("statistics", NOW, since=dt.datetime(2026, 10, 20, tzinfo=dt.UTC)) == [READ]


def test_the_schedule_reads_a_fortnight(tmp_path: Path, parsed: list[str]) -> None:
    """Its cadences are a week at most: an attempt older than the window would be due all the same."""
    log = CollectLog(tmp_path / "collect")
    for at in (NOW - dt.timedelta(days=70), NOW - dt.timedelta(days=40), READ):
        log.append(run(at))
    what_is_due(LakeStore(tmp_path / "lake"), log, NOW)
    assert set(parsed) == {f"{NOW:%Y-%m}.jsonl"}
    assert may_read("probable_lineups", log, NOW + dt.timedelta(minutes=20))
    assert not may_read("probable_lineups", log, READ + dt.timedelta(minutes=5))
