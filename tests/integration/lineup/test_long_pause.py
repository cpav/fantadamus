"""A pause longer than an answer's window, as over a winter break: found by the code review (task 9.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.contracts.xy.season import TeamSeasonPayload
from fantadamus.domains import facts
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.season.silver import TEAM_SEASONS
from fantadamus.web.fetch import Response
from tests.collect_harness import STATS_ROUTE
from tests.collect_pages import FcoMatch
from tests.lineup_harness import READ, Round, a_round
from tests.xy_harness import CLUBS, NOW, TAKERS, TEAM_TABLE, send

pytestmark = pytest.mark.anyio

FAR = (
    FcoMatch("Alfa", "Beta", kickoff="30/12/2026 15:00"),
    FcoMatch("Gamma", "Delta", kickoff="30/12/2026 18:00"),
)


async def _table_again(here: Round) -> None:
    """Claude rereads the two pages the collector doesn't, as a refresh plan asks."""
    for tool, payload in (("submit_team_season", TEAM_TABLE), ("submit_penalty_takers", TAKERS)):
        assert not (await send(here.client, tool, payload, here.clock.now)).is_error


async def test_unchanged_pages_still_answer_after_a_long_pause(tmp_path: Path) -> None:
    """An unchanged page stores nothing, so its last read can leave the window. It's stored again then."""
    async with a_round(tmp_path, matches=FAR) as here:
        first = await here.ask()
        assert first["status"] == "lineup", first
        here.clock.now = NOW + FACTS_WINDOW + dt.timedelta(days=6)
        await _table_again(here)
        later = await here.ask()
    assert later["status"] == "lineup", later


async def test_a_squad_nobody_knows_asks_for_the_statistics(tmp_path: Path) -> None:
    """If the statistics page is down as well, the plan says so, rather than asking for nothing."""
    async with a_round(tmp_path, matches=FAR) as here:
        await here.ask()
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(500, {}, b"")
        here.clock.now = NOW + FACTS_WINDOW + dt.timedelta(days=6)
        await _table_again(here)
        later = await here.ask()
    assert later["status"] == "refresh", later
    assert "player_season" in {item["fact"] for item in later["refresh"]}


async def test_a_warning_about_a_club_appears_once(tmp_path: Path) -> None:
    """Sources disagreeing on a club's table is one fact, however many of its players the squad has."""
    table = {**TEAM_TABLE, "teams": [{**TEAM_TABLE["teams"][0], "goals_for": 1}, *TEAM_TABLE["teams"][1:]]}
    other_page = "https://www.fantacalcio-online.com/classifica"
    async with a_round(tmp_path) as here:
        facts.submit(
            here.store,
            TEAM_SEASONS,
            TeamSeasonPayload.model_validate(table),
            source_url=other_page,
            captured_at=READ,
            published_at=None,
            allowed_hosts=["www.fantacalcio-online.com"],
            clock=here.clock,
            submitted_by="user-1",
            clubs=CLUBS,
        )
        result = await here.ask()
    warnings = [line for line in result["lineup"]["warnings"] if "Sources disagree" in line]
    assert len(warnings) == 1, warnings
