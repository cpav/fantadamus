"""Shared by the `mvp-next-round` tests: the round page as the site shows it over time, and the schedule's
runs over it (design C4). Clubs and players are invented."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures.gold import next_round
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import collect_due
from fantadamus.web.collector import Collector, CollectReport
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, FakeWeb, round_collector
from tests.collect_pages import FcoMatch, fco_round_page
from tests.xy_harness import SetClock

BASE = "https://example.org"
ROBOTS = BASE + "/robots.txt"
PAGE = BASE + ROUND_ROUTE
NO_ROBOTS = Response(404, {}, b"")
HOUR, MINUTE = dt.timedelta(hours=1), dt.timedelta(minutes=1)
DAY, RUN = 24 * HOUR, 15 * MINUTE
FIRST = dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
"""Round 10's deadline: 15:00 in Rome."""
MOVES_ON = FIRST + dt.timedelta(hours=4, minutes=21)
"""When the page moves on to round 11: as soon after the deadline as on 31 October."""
ROUND_10 = (FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="02/11/2026 20:45"))
Shows = Callable[[dt.datetime], Response | Exception]
"""What the site answers for the round page at a time."""


def rome(when: dt.datetime) -> str:
    """A kickoff as the page writes it: Italian winter time, an hour ahead of UTC."""
    return f"{when + HOUR:%d/%m/%Y %H:%M}"


def round_page(round: int, *matches: FcoMatch) -> Response:
    return Response(200, HTML, fco_round_page(*matches, round=round).encode())


def round_11(deadline: dt.datetime, *, early: bool) -> tuple[FcoMatch, FcoMatch]:
    """Round 11's two matches, the first at `deadline`; `early`: its fixtures alone, before any lineup or
    odds."""
    if early:
        return (
            FcoMatch("Beta", "Gamma", kickoff=rome(deadline), odds=None, lineups=False),
            FcoMatch("Delta", "Alfa", kickoff=rome(deadline + 2 * HOUR), odds=None, lineups=False),
        )
    return (
        FcoMatch("Beta", "Gamma", kickoff=rome(deadline)),
        FcoMatch("Delta", "Alfa", kickoff=rome(deadline + 2 * HOUR)),
    )


def moving_on(
    deadline: dt.datetime, *, at: dt.datetime = MOVES_ON, published: dt.datetime | None = None
) -> Shows:
    """The site: round 10 until `at`, then round 11, whose deadline is `deadline`, its fixtures alone until
    `published` (by default 80 hours before that deadline)."""
    out = published if published is not None else deadline - 80 * HOUR

    def shows(when: dt.datetime) -> Response:
        if when < at:
            return round_page(10, *ROUND_10)
        return round_page(11, *round_11(deadline, early=when < out))

    return shows


@dataclass
class Schedule:
    store: LakeStore
    log: CollectLog
    collector: Collector
    clock: SetClock
    web: FakeWeb
    shows: Shows

    def run(self, when: dt.datetime) -> CollectReport | None:
        """The schedule's run at `when`, the site showing what it shows then; None when nothing was due."""
        self.clock.now = when
        self.web.routes = {**self.web.routes, PAGE: self.shows(when)}
        return collect_due(self.collector, self.log)

    def runs(
        self, start: dt.datetime, end: dt.datetime, every: dt.timedelta = RUN
    ) -> list[tuple[dt.datetime, CollectReport]]:
        """The runs from `start` until `end`, `every` apart: those that read something."""
        found = []
        when = start
        while when < end:
            report = self.run(when)
            if report is not None:
                found.append((when, report))
            when += every
        return found

    def next_round(self, at: dt.datetime) -> int | None:
        return next_round(read_silver(self.store, FIXTURES), at)


def a_schedule(tmp_path: Path, shows: Shows, *, enabled: bool = True) -> Schedule:
    """The schedule over an empty lake, reading the round page alone, as the site `shows` it."""
    store, log, clock = LakeStore(tmp_path / "lake"), CollectLog(tmp_path / "collect"), SetClock(FIRST)
    web = FakeWeb({ROBOTS: NO_ROBOTS})
    collector = round_collector(
        store, BASE, tmp_path / "robots", transport=web, hosts=["example.org"], clock=clock, enabled=enabled
    )
    return Schedule(store, log, collector, clock, web, shows)
