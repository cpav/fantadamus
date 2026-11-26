"""mvp-next-round AT-5: two rounds whose deadlines are three days apart: the second is known before its alert
window opens, and an official lineup stored in the window sends its alert (R1.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures.gold import deadline, next_round
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.web.cadence import collect_due
from fantadamus.web.collector import CollectReport
from fantadamus.web.fetch import Response
from tests.alerts_harness import DEADLINE, Shown, alerts, check
from tests.collect_harness import HTML, ROUND_ROUTE
from tests.collect_pages import FcoMatch, fco_round_page, squad
from tests.lineup_harness import Round, a_round

pytestmark = pytest.mark.anyio
HOUR = dt.timedelta(hours=1)
SECOND = DEADLINE + dt.timedelta(days=3)
"""Round 11's deadline: the Tuesday after round 10's Saturday, at 15:00 in Rome."""


def _round_11(here: Round, *, early: bool = False, benched: str | None = None) -> None:
    """Round 11's page: `early`, its fixtures alone; `benched`, its official lineups out with him on the
    bench and his club's forward off the bench in his place."""
    marked: list[str] = []
    if benched is not None:
        for club in ("Alfa", "Gamma"):
            eleven = [name for name in squad(club)[:11] if name != benched]
            marked += [*eleven, *([f"{club} Tredici"] if len(eleven) < 11 else [])]
    if early:
        matches = (
            FcoMatch("Alfa", "Gamma", kickoff="03/11/2026 15:00", odds=None, lineups=False),
            FcoMatch("Beta", "Delta", kickoff="03/11/2026 18:00", odds=None, lineups=False),
        )
    else:
        matches = (
            FcoMatch("Alfa", "Gamma", kickoff="03/11/2026 15:00", marked=tuple(marked)),
            FcoMatch("Beta", "Delta", kickoff="03/11/2026 18:00"),
        )
    page = fco_round_page(*matches, round=11)
    here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, page.encode())


def _run(here: Round, at: dt.datetime) -> CollectReport | None:
    """The schedule's run at `at`."""
    here.clock.now = at
    collector = here.calibrator.collector
    assert collector is not None
    return collect_due(collector, here.collect_log)


async def test_at5_a_round_three_days_on_is_found_and_alerts(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        _run(here, DEADLINE - HOUR / 4)
        last = here.collect_log.last_answered(DEADLINE)
        assert last is not None
        _round_11(here, early=True)
        _run(here, last + 24 * HOUR)
        fixtures = read_silver(here.store, FIXTURES)
        found_at = here.clock.now
        assert next_round(fixtures, found_at) == 11
        assert deadline(fixtures, 11, found_at) == SECOND
        assert found_at < SECOND - 24 * HOUR  # before its alert window opens

        _round_11(here)
        shown = Shown()
        first = check(here, _run(here, SECOND - 23 * HOUR), shown)
        assert first.outcome == "baseline", first  # nobody asked this round: the first call is kept
        [baseline] = alerts(here).read()
        stored = here.squads.get("user-1")
        assert stored is not None
        playing = next(
            player
            for player in stored.players
            if player.player_id in baseline.call.starters
            and player.club in ("Alfa", "Gamma")
            and player.role != "P"
        )
        _round_11(here, benched=playing.name)
        checked = check(here, _run(here, SECOND - HOUR), shown)
    assert checked.outcome == "sent", checked
    [(title, subtitle, _)] = shown.sent
    assert (title, subtitle) == ("Fantadamus · Round 11", "Official lineup out")
