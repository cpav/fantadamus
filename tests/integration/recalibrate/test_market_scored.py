"""A finished round scores the market's match chances beside the players', from the odds held before each
kickoff and the goals its keepers' rows show (mvp-recalibrate R7.1; design C7)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.calibration import (
    AWAY_WIN,
    BOTH_SCORE,
    DRAW,
    HOME_WIN,
    SIDE_CLEAN_SHEET,
    THREE_OR_MORE,
)
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE
from tests.collect_pages import FcoMatch, fco_round_page
from tests.lineup_harness import MATCHES, a_round, stats_after, the_next_round

pytestmark = pytest.mark.anyio

ROUND_10 = "/probabili-formazioni/10-giornata"
BETWEEN = dt.datetime(2026, 10, 31, 15, 0, tzinfo=dt.UTC)
"""Alfa v Beta kicked off at 14:00 UTC, Gamma v Delta at 17:00."""


async def test_a_round_scores_the_market(tmp_path: Path) -> None:
    """Alfa's keeper conceded one and the others none: Alfa 0 Beta 1, Gamma 0 Delta 0. Odds read after Alfa
    v Beta kicked off, before Gamma v Delta did, aren't Alfa v Beta's forecast: its 2.10 before it is."""
    finished = fco_round_page(*(FcoMatch(m.home, m.away, kickoff=m.kickoff, confirmed=True) for m in MATCHES))
    later = fco_round_page(
        *(FcoMatch(m.home, m.away, kickoff=m.kickoff, odds=("1,20", "6,00", "12,00")) for m in MATCHES)
    )
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, later.encode())
        here.clock.now = BETWEEN
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = BETWEEN + dt.timedelta(days=1, minutes=1)  # the statistics page is read daily
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    assert report.market is not None
    happened = {
        chance.chance: (chance.count, round(sum(bucket.happened * bucket.count for bucket in chance.buckets)))
        for chance in report.market.scored
    }
    assert happened == {
        HOME_WIN: (2, 0),
        DRAW: (2, 1),
        AWAY_WIN: (2, 1),
        SIDE_CLEAN_SHEET: (4, 3),
        THREE_OR_MORE: (2, 0),
        BOTH_SCORE: (2, 0),
    }
    assert report.market.unscored == []
    home_win = next(chance for chance in report.market.scored if chance.chance == HOME_WIN)
    said = sorted(bucket.said for bucket in home_win.buckets for _ in range(bucket.count))
    assert said[0] < 0.5 < said[1]  # Alfa v Beta at about 1 / 2.10; Gamma v Delta's later odds were before it
