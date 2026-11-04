"""AT-10: an override returns that lineup with its cost, from the same simulated rounds (design C8; R2.3,
R3.5)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from tests.lineup_harness import a_round
from tests.xy_harness import NOW

pytestmark = pytest.mark.anyio


def _starters(lineup: dict[str, Any]) -> set[str]:
    return {part["name"] for part in lineup["starters"]}


def _bench(lineup: dict[str, Any]) -> set[str]:
    return {part["name"] for part in lineup["bench"]}


async def test_at10_an_override_and_its_cost(tmp_path: Path) -> None:
    """Forcing a player in returns that lineup, and the cost against the advice in points and threshold
    chances."""
    async with a_round(tmp_path) as here:
        await here.set_rules(other_rules=["defence modifier"])
        advised = (await here.ask())["lineup"]
        worst = min(
            (part for part in advised["bench"] if part["role"] == "D" and part["value"] > 0),
            key=lambda part: part["value"],
        )
        result = await here.ask(start=[worst["name"]])
    assert advised["override"] is None
    assert result["status"] == "lineup", result
    lineup = result["lineup"]
    assert worst["name"] in _starters(lineup)
    override = lineup["override"]
    best = advised["formations"][0]
    assert override["advised_formation"] == best["formation"]
    assert override["advised_expected"] == best["mean"]
    assert override["cost"] == pytest.approx(best["mean"] - lineup["expected"], abs=0.02)
    assert override["cost"] > 0
    assert override["fantasy_goals_cost"] == pytest.approx(
        best["fantasy_goals"] - lineup["fantasy_goals"], abs=0.002
    )
    assert override["advised_starters"] == [part["name"] for part in advised["starters"]]
    chances = {mark["points"]: mark["chance"] for mark in lineup["thresholds"]}
    assert {mark["points"]: (mark["advised"], mark["chosen"]) for mark in override["thresholds"]} == {
        mark["points"]: (mark["chance"], chances[mark["points"]]) for mark in best["thresholds"]
    }
    # A league rule left out is named, the table stays the advice's, and the cost is the formation call.
    assert any("defence modifier" in warning for warning in lineup["warnings"])
    assert lineup["formations"] == advised["formations"]
    assert all(call["kind"] == "place" for call in lineup["calls"])


async def test_at10_another_formation(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        other = next(
            entry["formation"]
            for entry in advised["formations"]
            if entry["formation"] != advised["formation"]
        )
        here.clock.now = NOW + dt.timedelta(minutes=1)
        lineup = (await here.ask(formation=other))["lineup"]
    assert lineup["moved"] == []  # the cost says what matters here
    assert lineup["formation"] == other
    assert lineup["override"]["advised_formation"] == advised["formation"]
    same = next(entry for entry in advised["formations"] if entry["formation"] == other)
    assert lineup["expected"] == same["mean"]  # the same rounds: the same number as in the advice's own table
    assert lineup["override"]["cost"] == pytest.approx(advised["expected"] - same["mean"], abs=0.02)


async def test_at10_asking_for_the_advised_formation_costs_nothing(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        lineup = (await here.ask(formation=advised["formation"]))["lineup"]
    assert lineup["override"]["cost"] == 0
    assert lineup["starters"] == advised["starters"]


async def test_at10_leaving_a_player_out(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        star = next(part["name"] for part in advised["starters"] if part["role"] == "A")
        lineup = (await here.ask(leave_out=[star]))["lineup"]
    assert star not in _starters(lineup)
    assert star in _bench(lineup)  # out of the eleven, still there to come on
    assert lineup["override"]["cost"] > 0


async def test_at10_start_finds_its_best_formation(tmp_path: Path) -> None:
    """Without a formation, the forced player goes wherever the lineup does best."""
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        fifth = [part for part in advised["bench"] if part["role"] == "D"]
        everyone = [part["name"] for part in advised["starters"] if part["role"] == "D"] + [
            part["name"] for part in fifth[:2]
        ]
        forced = everyone[:5]
        lineup = (await here.ask(start=forced))["lineup"]
    assert lineup["formation"].startswith("5-")
    assert set(forced) <= _starters(lineup)


async def test_at10_names_are_matched_within_the_squad(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        star = next(part["name"] for part in advised["starters"] if part["role"] == "A")
        by_surname = (await here.ask(leave_out=[star.split()[1] + " " + star.split()[0]]))["lineup"]
    assert star not in _starters(by_surname)


async def test_at10_an_override_is_logged_with_its_cost(tmp_path: Path) -> None:
    """R7.1 and §A8: the advice is kept beside what was asked for, and what moved ignores overrides."""
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        other = next(
            entry["formation"]
            for entry in advised["formations"]
            if entry["formation"] != advised["formation"]
        )
        here.clock.now = NOW + dt.timedelta(minutes=1)
        chosen = (await here.ask(formation=other))["lineup"]
        [plain, forced] = here.log.read()
        here.clock.now = NOW + dt.timedelta(minutes=2)
        again = (await here.ask())["lineup"]
    assert plain.override_cost is None
    assert forced.override_cost == pytest.approx(chosen["override"]["cost"], abs=0.01)
    assert forced.formation == other
    assert forced.starters == [part["player_id"] for part in chosen["starters"]]
    assert forced.advised_starters == [part["player_id"] for part in advised["starters"]]
    assert plain.starters == [part["player_id"] for part in advised["starters"]]
    assert plain.advised_starters is None
    assert again["moved"] == []  # compared with the last advice, not the override


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        ({"formation": "2-4-4"}, "2-4-4 isn't a formation this league allows"),
        ({"start": ["Nessuno Mai"]}, "Nessuno Mai isn't in this squad"),
        ({"leave_out": ["Nessuno Mai"]}, "Nessuno Mai isn't in this squad"),
        ({"start": ["Alfa Uno", "Gamma Uno"]}, "told to start"),
        ({"start": ["Alfa Uno"], "leave_out": ["Alfa Uno"]}, "both start and be left out"),
        ({"leave_out": ["Alfa Uno", "Gamma Uno", "Beta Uno"]}, "keepers"),
    ],
)
async def test_override_refused(tmp_path: Path, options: dict[str, Any], reason: str) -> None:
    async with a_round(tmp_path) as here:
        result = await here.ask(**options)
    assert result["status"] == "refused", result
    assert reason in result["message"]
    assert result["lineup"] is None


async def test_a_name_that_could_be_two_players_is_asked_about(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        result = await here.ask(start=["Uno"])
    assert result["status"] == "choose", result
    assert {player["name"] for player in result["unresolved"]["Uno"]} == {"Alfa Uno", "Beta Uno", "Gamma Uno"}
    assert result["lineup"] is None
