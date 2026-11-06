"""mvp-lineup task 9.1, found on a real round: one line a log can't read must not stop every answer. It can be
half-written, or written by a newer version than the one reading it."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import pytest

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import Decision, DecisionLog
from fantadamus.league.rules import CLASSIC, StoredRules
from fantadamus.web.collector import CollectReport, PageReport
from tests.lineup_harness import a_round
from tests.xy_harness import NOW

BAD_LINES = (
    "not json at all",
    '{"started_at": "2026-11-06T20:30:00Z", "finished_at"',  # half-written
    '{"started_at": "2026-11-06T20:30:00Z", "finished_at": "2026-11-06T20:30:01Z", "round": null, '
    '"pages": [{"url": "https://example.org/", "page": "a kind from a newer version", "outcome": "stored"}]}',
)


def _report(minute: int) -> CollectReport:
    at = dt.datetime(2026, 11, 6, 20, minute, tzinfo=dt.UTC)
    page = PageReport(url="https://example.org/round", outcome="stored", fetched_at=at)
    return CollectReport(started_at=at, finished_at=at, round=None, pages=[page])


def _decision(round: int) -> Decision:
    rules = StoredRules(user="owner", rules=CLASSIC, saved_at=NOW)
    return Decision(
        as_of=NOW, logged_at=NOW, user="owner", round=round, players=[], rules=rules, content_hashes=[]
    )


def _add(path: Path, *lines: str) -> None:
    with path.open("a", encoding="utf-8") as log:
        log.writelines(line + "\n" for line in lines)


def test_the_collect_log_skips_a_line_it_cant_read(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    log = CollectLog(tmp_path)
    log.append(_report(1))
    _add(tmp_path / "2026-11.jsonl", *BAD_LINES)
    log.append(_report(2))
    with caplog.at_level(logging.WARNING):
        runs = log.runs()
    skipped = [record.getMessage() for record in caplog.records]
    assert [run.started_at.minute for run in runs] == [1, 2]
    assert log.last_attempt(_report(9).started_at) == _report(2).started_at
    assert skipped == [f"Skipped 2026-11.jsonl line {number}: it can't be read" for number in (2, 3, 4)]


def test_the_decision_log_skips_a_line_it_cant_read(tmp_path: Path) -> None:
    log = DecisionLog(tmp_path)
    path = log.append(_decision(1))
    _add(path, *BAD_LINES)
    log.append(_decision(2))
    assert [decision.round for decision in log.read()] == [1, 2]


def test_a_bad_byte_costs_only_its_line(tmp_path: Path) -> None:
    log = CollectLog(tmp_path)
    log.append(_report(1))
    with (tmp_path / "2026-11.jsonl").open("ab") as raw:
        raw.write(b"\xff\xfe broken\n")
    log.append(_report(2))
    assert [run.started_at.minute for run in log.runs()] == [1, 2]


def test_a_blank_line_isnt_worth_a_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    log = DecisionLog(tmp_path)
    _add(log.append(_decision(1)), "", "   ")
    with caplog.at_level(logging.WARNING):
        assert len(log.read()) == 1
    assert not caplog.records


def test_a_folder_with_no_log_yet_reads_as_empty(tmp_path: Path) -> None:
    assert CollectLog(tmp_path / "none").runs() == []
    assert DecisionLog(tmp_path / "none").read() == []


@pytest.mark.anyio
async def test_a_bad_line_doesnt_stop_the_answer(tmp_path: Path) -> None:
    """Both logs are read on every lineup: this is the failure as a player would have met it."""
    async with a_round(tmp_path) as here:
        first = await here.ask()
        assert first["status"] == "lineup"
        for log_file in (*here.collect_log.root.glob("*.jsonl"), *here.log.root.glob("*.jsonl")):
            _add(log_file, *BAD_LINES)
        second = await here.ask()
    assert second["status"] == "lineup"
    assert second["lineup"]["formation"] == first["lineup"]["formation"]
