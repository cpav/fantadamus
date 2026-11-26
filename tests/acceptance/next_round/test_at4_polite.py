"""mvp-next-round AT-4: a daily read that gets no answer is due again at the next run; one that got the site's
answer waits 24 hours. Each run asks for the page at most once, after robots.txt and a second apart; with the
page switched off, nothing is asked (R2.1 to R2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.web.cadence import what_is_due
from fantadamus.web.collector import Collector, CollectorConfig
from fantadamus.web.fetch import Fetcher, Response
from tests.collect_harness import HTML, FakeTime, FakeWeb
from tests.next_round_harness import (
    BASE,
    DAY,
    FIRST,
    HOUR,
    MINUTE,
    NO_ROBOTS,
    PAGE,
    ROBOTS,
    ROUND_10,
    RUN,
    Schedule,
    a_schedule,
    round_page,
)
from tests.xy_harness import CLUBS

REFUSAL = Response(200, {}, b"User-agent: *\nDisallow: /probabili-formazioni/\n")
READ = round_page(10, *ROUND_10)
CASES: dict[str, tuple[Response | Exception, Response | Exception, str, bool]] = {
    "no answer": (NO_ROBOTS, TimeoutError("timed out"), "failed", True),
    "a server error": (NO_ROBOTS, Response(500, {}, b""), "failed", True),
    "robots.txt gets no answer": (TimeoutError("timed out"), READ, "failed", True),
    "robots.txt refuses it": (REFUSAL, READ, "disallowed", False),
    "a block": (NO_ROBOTS, Response(403, {}, b""), "blocked", False),
    "the page is gone": (NO_ROBOTS, Response(404, {}, b""), "missing", False),
    "an unreadable page": (NO_ROBOTS, Response(200, HTML, b"<html></html>"), "unreadable", False),
}
"""robots.txt and the page the day after a read, the outcome, and whether the page is due at the next run."""


@pytest.mark.parametrize("case", list(CASES))
def test_at4_a_failed_read_is_tried_again_at_the_next_run(tmp_path: Path, case: str) -> None:
    robots, page, outcome, at_the_next_run = CASES[case]
    answer: list[Response | Exception] = [READ]
    here = a_schedule(tmp_path, lambda _: answer[0])
    here.run(FIRST - HOUR)
    answer[0] = page
    here.web.routes = {**here.web.routes, ROBOTS: robots}  # a new day: robots.txt is asked again
    day_after = FIRST - HOUR + DAY
    report = here.run(day_after)
    assert report is not None
    assert [read.outcome for read in report.pages] == [outcome]
    assert ("fixtures" in what_is_due(here.store, here.log, day_after + RUN)) is at_the_next_run
    assert "fixtures" in what_is_due(here.store, here.log, day_after + DAY)


def test_at4_each_run_asks_once_after_robots_and_a_second_apart(tmp_path: Path) -> None:
    """In round 10's last day several of the page's facts are due at once; each run still asks for the page
    once, robots.txt first and a second before it."""
    here = a_schedule(tmp_path, lambda _: READ)
    time = FakeTime()
    web = FakeWeb({ROBOTS: NO_ROBOTS, PAGE: READ}, time)
    config = CollectorConfig(current_round=PAGE, round=BASE + "/probabili-formazioni/{round}-giornata")
    collector = Collector(
        fetcher=lambda: Fetcher(
            allowed_hosts=["example.org"],
            clock=here.clock,
            monotonic=time.monotonic,
            sleep=time.sleep,
            transport=web,
            robots_cache=tmp_path / "robots",
        ),
        lake=here.store,
        clubs=CLUBS,
        config=config,
        allowed_hosts=("example.org",),
        clock=here.clock,
    )
    timed = Schedule(here.store, here.log, collector, here.clock, web, lambda _: READ)
    runs = timed.runs(FIRST - 26 * HOUR, FIRST)
    assert any(len(run.due) > 1 for _, run in runs)
    pages = [url for url, _, _ in web.calls if url == PAGE]
    assert len(pages) == len(runs)
    [(robots, asked), (page, then)] = [(url, when) for url, _, when in web.calls[:2]]
    assert (robots, page) == (ROBOTS, PAGE)
    assert then - asked >= 1.0


def test_at4_switched_off_nothing_is_asked(tmp_path: Path) -> None:
    here = a_schedule(tmp_path, lambda _: READ, enabled=False)
    report = here.run(FIRST)
    assert report is not None
    assert [read.outcome for read in report.pages] == ["switched off"]
    assert here.web.calls == []
    assert "fixtures" not in what_is_due(here.store, here.log, FIRST + DAY - MINUTE)
