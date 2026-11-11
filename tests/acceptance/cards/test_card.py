"""AT-1, AT-8 and AT-9 of mvp-cards: `match_card` through the tools, asked by one club or both, for a club
with no match and for a round past its deadline; its numbers the same as `player_outlook`'s; and logged for
the calibration (design C5; R1, R6.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.calibration import last_told
from tests.collect_pages import FcoMatch
from tests.lineup_harness import SQUAD, Round, a_round, player_id
from tests.xy_harness import classic_with

pytestmark = pytest.mark.anyio

AFTER_THE_DEADLINE = dt.datetime(2026, 10, 31, 16, 0, tzinfo=dt.UTC)  # round 10 locked at 14:00


async def card(here: Round, **args: Any) -> dict[str, Any]:
    result = await here.client.call_tool("match_card", args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_at1_by_two_clubs_and_by_one(tmp_path: Path) -> None:
    """One club, or both in either order and any accepted spelling: the same match's card, with its context
    line, both sides' elevens and the numbers."""
    async with a_round(tmp_path) as here:
        by_one = await card(here, club="Alfa")
        by_two = await card(here, club="BETA", other_club="alfa")
    assert by_one["status"] == "card", by_one
    found = by_one["card"]
    assert (found["round"], found["match"]) == (10, "Alfa v Beta")
    assert found["kickoff"].startswith("2026-10-31T15:00:00+01:00")  # in Europe/Rome
    assert found["deadline"].startswith("2026-10-31T15:00:00+01:00")
    assert not found["past_deadline"]
    assert found["updated"]["newest"] >= found["updated"]["oldest"]
    assert [side["club"] for side in found["sides"]] == ["Alfa", "Beta"]
    assert all(len(side["eleven"]) == 11 for side in found["sides"])
    assert found["numbers"]["home"]["p_win"] > 0
    assert found["sources"]
    assert not found["classic_rules"]  # the league's own rules are stored
    playing = {player_id(*name.split()) for name in SQUAD if name.split()[0] in ("Alfa", "Beta")}
    assert set(found["yours"]) == playing  # the user's players in the match, each named on the card
    assert set(found["yours"]) <= {player["player_id"] for player in found["players"]}
    assert by_two["card"]["match"] == "Alfa v Beta"
    numbers = [value for player in found["players"] for value in player.values() if isinstance(value, float)]
    assert numbers
    assert all(round(value, 3) == value for value in numbers)  # three decimals, to stay within its size


async def test_at1_a_club_with_no_match(tmp_path: Path) -> None:
    """A club with no match in the round says so; an unknown club, or two that don't meet, is refused."""
    async with a_round(tmp_path, matches=(FcoMatch("Alfa", "Beta"),)) as here:
        idle = await card(here, club="Gamma")
        unknown = await card(here, club="Omega")
        apart = await card(here, club="Alfa", other_club="Gamma")
        itself = await card(here, club="Alfa", other_club="ALFA")
    assert idle["status"] == "no_match"
    assert "Gamma" in idle["message"]
    assert "round 10" in idle["message"]
    assert unknown["status"] == "refused"
    assert "Omega" in unknown["message"]
    assert apart["status"] == "refused"
    assert "don't meet" in apart["message"]
    assert itself["status"] == "refused"
    assert "itself" in itself["message"]


async def test_at1_kicked_off(tmp_path: Path) -> None:
    """Past its round's deadline a match's card is the one it had then, said so, and nothing is logged: a
    forecast's job ends there."""
    async with a_round(tmp_path) as here:
        await card(here, club="Alfa")
        logged = len(here.log.read())
        here.clock.now = AFTER_THE_DEADLINE
        late = await card(here, club="Alfa", other_club="Beta")
        assert len(here.log.read()) == logged
    assert late["status"] == "card", late
    assert late["card"]["past_deadline"]
    assert "deadline" in late["message"]
    assert late["card"]["round"] == 10
    assert all(len(side["eleven"]) == 11 for side in late["card"]["sides"])


async def test_at8_the_same_numbers_as_an_outlook(tmp_path: Path) -> None:
    """Every player on the card has the chances and the worth `player_outlook` gives him at the same time."""
    async with a_round(tmp_path) as here:
        rules = classic_with(goal=4.0, lineup=None)  # not Classic's: a card must price on the league's own
        assert not (await here.client.call_tool("set_league_rules", {"rules": rules})).is_error
        await here.ask()  # the facts, collected once
        at = here.clock.now.isoformat()
        found = (await card(here, club="Alfa", as_of=at))["card"]
        outlooks = {}
        for player in found["players"]:
            result = await here.client.call_tool("player_outlook", {"player": player["name"], "as_of": at})
            content = result.structured_content
            assert content is not None
            outlooks[player["name"]] = content["answer"]["players"][0]["value"]
    for player in found["players"]:  # a card rounds to three decimals, to stay within its size
        value = outlooks[player["name"]]
        assert player["p_start"] == pytest.approx(value["p_start"], abs=1e-3), player["name"]
        assert player["key"] == pytest.approx(value["key"], abs=1e-3), player["name"]
        if player["role"] != "P":
            assert player["p_scores_if_starts"] == pytest.approx(value["p_scores"], abs=1e-3), player["name"]
        else:
            assert player["p_clean_sheet"] == pytest.approx(value["p_clean_sheet"], abs=1e-3), player["name"]


async def test_at9_logged_and_counted(tmp_path: Path) -> None:
    """A card asked before kickoff logs every player it shows, the user's or not, so the round's report counts
    what users were told about them."""
    async with a_round(tmp_path) as here:
        found = (await card(here, club="Alfa"))["card"]
        decisions = here.log.read()
    cards = [decision for decision in decisions if decision.kind == "card"]
    assert len(cards) == 1
    shown = {player["player_id"] for player in found["players"]}
    assert {logged.player_id for logged in cards[0].players} == shown
    beta_defender = player_id("Beta", "Due")  # not in the user's squad
    assert beta_defender in shown
    kickoff = dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
    assert beta_defender in last_told(decisions, 10, lambda _: kickoff)
