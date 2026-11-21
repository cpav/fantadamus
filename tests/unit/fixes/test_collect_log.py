"""mvp-fixes task 1.3: a run counts as a page's read only when it got the site's answer; lines logged before
this slice read as they are (design C2; R1.2)."""

from __future__ import annotations

import datetime as dt

from fantadamus.lake.collect_log import ANSWERED, FAILED, newest
from fantadamus.web.collector import CollectReport, PageKind, PageReport
from fantadamus.web.collector import Outcome as PageOutcome

T = dt.datetime(2026, 11, 21, 5, 1, tzinfo=dt.UTC)
HOUR = dt.timedelta(hours=1)


def _run(at: dt.datetime, *pages: tuple[PageKind, PageOutcome]) -> CollectReport:
    return CollectReport(
        started_at=at,
        finished_at=at,
        round=None,
        pages=[
            PageReport(url=f"https://site.example/{kind}", page=kind, outcome=outcome)
            for kind, outcome in pages
        ],
    )


RUNS = [
    _run(T - 36 * HOUR, ("round", "unchanged"), ("statistics", "unchanged")),
    _run(T, ("round", "stored"), ("statistics", "failed")),
]


def test_a_failed_try_is_not_the_last_answered() -> None:
    assert newest(RUNS, T + HOUR, "statistics", ANSWERED) == T - 36 * HOUR
    assert newest(RUNS, T + HOUR, "round", ANSWERED) == T
    assert "failed" not in ANSWERED
    assert {"stored", "unchanged", "rejected", "unreadable", "disallowed", "blocked", "missing"} <= ANSWERED


def test_last_failed() -> None:
    assert newest(RUNS, T + HOUR, "statistics", FAILED) == T
    assert newest(RUNS, T - HOUR, "statistics", FAILED) is None  # as it stood before it
    assert newest(RUNS, T + HOUR, "takers", ANSWERED) is None  # never tried


def test_old_lines_read_as_they_are() -> None:
    """A run logged before this slice, as on 21 November: its unreadable robots.txt was logged as disallowed,
    and that line still reads, and still counts."""
    line = (
        '{"started_at": "2026-11-21T05:01:42Z", "finished_at": "2026-11-21T07:02:14Z", "round": null, '
        '"due": ["player_season"], "pages": [{"url": "https://site.example/statistiche-serie-a", '
        '"page": "statistics", "outcome": "disallowed", '
        '"reason": "robots.txt disallows https://site.example/statistiche-serie-a", '
        '"for_claude": ["player_season"]}]}'
    )
    run = CollectReport.model_validate_json(line)
    assert newest([run], T + 3 * HOUR, "statistics", ANSWERED) == run.started_at
