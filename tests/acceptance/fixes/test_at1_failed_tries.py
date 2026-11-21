"""mvp-fixes AT-1: a try that got no answer from the site is tried again at the next run; the site's own
answers, a refusal by its robots.txt, a block or a page it says is gone, keep counting as the page's read
(R1.1, R1.2, R1.4).

As on 21 November: a run that can't reach a host logs its pages as failed, and the schedule's next look, 15
minutes later, finds them due again, instead of a day later."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import what_is_due
from fantadamus.web.fetch import Response
from tests.collect_harness import FakeWeb, round_collector, ticking
from tests.xy_harness import NOW

BASE = "https://example.org"
ROBOTS = BASE + "/robots.txt"
CHAMPIONS = BASE + "/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase?action=raw"
NO_ROBOTS = Response(404, {}, b"")
NEXT_RUN = dt.timedelta(minutes=15)
CASES: dict[str, tuple[dict[str, Response | Exception], str, bool]] = {
    "robots.txt gets no answer": ({ROBOTS: TimeoutError("timed out")}, "failed", True),
    "robots.txt answers a server error": ({ROBOTS: Response(502, {}, b"")}, "failed", True),
    "the page answers a server error": (
        {ROBOTS: NO_ROBOTS, CHAMPIONS: Response(500, {}, b"")},
        "failed",
        True,
    ),
    "robots.txt refuses the page": (
        {ROBOTS: Response(200, {}, b"User-agent: *\nDisallow: /wiki/\n")},
        "disallowed",
        False,
    ),
    "the site blocks": ({ROBOTS: NO_ROBOTS, CHAMPIONS: Response(403, {}, b"")}, "blocked", False),
    "the page is gone": ({ROBOTS: NO_ROBOTS, CHAMPIONS: Response(404, {}, b"")}, "missing", False),
}


@pytest.mark.parametrize("case", list(CASES))
def test_at1_a_failed_try_is_tried_again_at_the_next_run(tmp_path: Path, case: str) -> None:
    routes, outcome, due_again = CASES[case]
    store, log = LakeStore(tmp_path / "lake"), CollectLog(tmp_path / "collect")
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(routes),
        hosts=["example.org"],
        clock=ticking(NOW),
        other_competitions=[CHAMPIONS],
    )
    assert "other_fixtures" in what_is_due(store, log, NOW)
    report = collector.collect(facts=["other_fixtures"])
    log.append(report)
    assert [page.outcome for page in report.pages] == [outcome]
    assert ("other_fixtures" in what_is_due(store, log, NOW + NEXT_RUN)) is due_again
