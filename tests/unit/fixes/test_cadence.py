"""mvp-fixes task 1.4: a page whose last try failed is due at the next run; an answer waits a while after a
failed try; a block still waits for the cadence (design C3; R1.2 to R1.4)."""

from __future__ import annotations

import datetime as dt

from fantadamus.lake.collect_log import ANSWERED, FAILED, newest
from fantadamus.web.cadence import RETRY_AFTER, due, may_read_after
from fantadamus.web.collector import CollectReport, PageKind, PageReport
from fantadamus.web.collector import Outcome as PageOutcome

T = dt.datetime(2026, 11, 21, 5, 1, tzinfo=dt.UTC)
HOUR, MINUTE = dt.timedelta(hours=1), dt.timedelta(minutes=1)
EVERY_OUTCOME = ANSWERED | FAILED


def _run(at: dt.datetime, kind: PageKind, outcome: PageOutcome) -> CollectReport:
    page = PageReport(url=f"https://site.example/{kind}", page=kind, outcome=outcome)
    return CollectReport(started_at=at, finished_at=at, round=None, pages=[page])


def test_a_failed_page_is_due_at_the_next_run() -> None:
    """21 November: the statistics page, read the day before, failed at 05:01. Counting only answered tries,
    it's due at the next run; counting every try, as before this slice, it waited a day."""
    runs = [_run(T - 33 * HOUR, "statistics", "unchanged"), _run(T, "statistics", "failed")]
    after = T + 15 * MINUTE
    assert due("player_season", newest(runs, after, "statistics", ANSWERED), after, None)
    assert not due("player_season", newest(runs, after, "statistics", EVERY_OUTCOME), after, None)


def test_an_answer_waits_after_a_failed_try() -> None:
    assert RETRY_AFTER == 15 * MINUTE
    stale = T - 30 * HOUR
    assert not may_read_after("statistics", stale, T, T + 10 * MINUTE)
    assert may_read_after("statistics", stale, T, T + RETRY_AFTER)
    assert may_read_after("statistics", stale, None, T)
    assert not may_read_after("statistics", T - 2 * HOUR, None, T)  # within its own interval, a day
    assert may_read_after("round", None, None, T)


def test_a_block_waits_for_the_cadence() -> None:
    """A site that said stop counts as a read: the page waits for its cadence, as before."""
    for outcome in ("blocked", "disallowed", "missing"):
        runs = [_run(T, "statistics", outcome)]
        after = T + 15 * MINUTE
        assert not due("player_season", newest(runs, after, "statistics", ANSWERED), after, None), outcome
        assert not may_read_after("statistics", newest(runs, after, "statistics", ANSWERED), None, after)
