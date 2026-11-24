"""mvp-fixes task 5.1: the review log keeps the user's app total and whether it differed, and a line logged
before the slice still reads, with none (design C8; R5.1, R5.3)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from fantadamus.domains.review import Reviewed, logged, record, review_choices
from fantadamus.lake.review_log import ReviewLog
from tests.review_choices import ADVICE, RULES, SQUAD, Stand

AT = dt.datetime(2026, 11, 24, 9, 0, tzinfo=dt.UTC)


def _reviewed() -> Reviewed:
    """The advice followed, every player worth 6."""
    stand = Stand({}, {}, captain_expected={}, captain_real={}, bench_expected={}, bench_real={})
    return review_choices(ADVICE, ADVICE, SQUAD, RULES, price=stand.price, score=stand.score)


def test_the_app_total_is_kept(tmp_path: Path) -> None:
    line = logged(
        _reviewed(),
        user="user-1",
        team="mine",
        round=12,
        as_of=AT,
        logged_at=AT,
        content_hashes=[],
        app_total=72.5,
        app_differs=True,
    )
    assert (line.app_total, line.app_differs) == (72.5, True)
    log = ReviewLog(tmp_path / "reviews")
    log.append(line)
    assert log.read() == [line]
    plain = logged(
        _reviewed(), user="user-1", team="mine", round=13, as_of=AT, logged_at=AT, content_hashes=[]
    )
    assert (plain.app_total, plain.app_differs) == (None, None)


def test_a_line_from_before_reads(tmp_path: Path) -> None:
    line = logged(
        _reviewed(), user="user-1", team="mine", round=11, as_of=AT, logged_at=AT, content_hashes=[]
    )
    before = json.loads(line.model_dump_json())
    del before["app_total"], before["app_differs"]  # as the log kept it before this slice
    folder = tmp_path / "reviews"
    folder.mkdir()
    (folder / "2026-11.jsonl").write_text(json.dumps(before) + "\n", encoding="utf-8")
    [read] = ReviewLog(folder).read()
    assert read == line
    assert (read.app_total, read.app_differs) == (None, None)
    found = record([read], user="user-1", team="mine")
    assert (found.rounds, found.app_rounds, found.app_matched) == (1, 0, 0)
