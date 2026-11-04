"""AT-5, AT-6, AT-9 and AT-14: the lineup itself (design C8; R3, R4.6, R5, R6.1)."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts.checks._common import run_command

from fantadamus.engine.simulate import Simulated, recommended
from tests.collect_pages import FcoMatch
from tests.lineup_data import lineup_rules
from tests.lineup_harness import MATCHES, SQUAD, a_round, rows
from tests.xy_harness import NOW, odds_for, send

pytestmark = pytest.mark.anyio


def _forward(goals: int) -> dict[str, Any]:
    return {"goals": goals, "assists": 3, "average_rating": 6.8}


def _defender() -> dict[str, Any]:
    return {"goals": 0, "assists": 0, "average_rating": 5.6}


async def test_at5_the_formation_falls_out_of_the_marginal_players(tmp_path: Path) -> None:
    """A strong third forward over a weak fourth defender picks three at the back and three up front."""
    strong = {
        f"{club}_{word}": _forward(6) for club in ("Beta", "Delta") for word in ("Nove", "Dieci", "Undici")
    }
    weak = {
        f"{club}_{word}": _defender()
        for club in ("Alfa", "Gamma")
        for word in ("Due", "Tre", "Quattro", "Cinque")
    }
    async with a_round(tmp_path, players=rows(**strong, **weak)) as here:
        lineup = (await here.ask())["lineup"]
    assert lineup["formation"] == "3-4-3"
    assert len({entry["formation"] for entry in lineup["formations"]}) == 7
    assert lineup["formations"][0]["formation"] == lineup["formation"]


def _result(formation: str, mean: float, goals: float) -> Simulated:
    return Simulated(
        formation=formation, mean=mean, low=mean - 8, high=mean + 8, fantasy_goals=goals, thresholds=[]
    )


def test_at5_a_head_to_head_and_a_total_points_league_can_differ() -> None:
    steady, risky = _result("4-4-2", 72.0, 1.1), _result("3-4-3", 71.0, 1.3)
    assert recommended([steady, risky], lineup_rules(format="head_to_head")).formation == "3-4-3"
    assert recommended([steady, risky], lineup_rules(format="total_points")).formation == "4-4-2"


async def test_at5_a_total_points_league_needs_no_thresholds(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.set_rules(format="total_points", thresholds=None)
        result = await here.ask()
    assert result["status"] == "lineup", result
    lineup = result["lineup"]
    assert lineup["thresholds"] == []
    assert lineup["formations"][0]["mean"] == max(entry["mean"] for entry in lineup["formations"])


async def test_at6_bench_and_keepers(tmp_path: Path) -> None:
    """An unrated backup with a higher key than his club's starter: the starter is fielded, the backup goes
    first on the bench, and it all comes from one call with each source once."""
    backup = {
        "Alfa_Dodici": {
            "role": "P",
            "mantra_role": "Por",
            "goals": 0,
            "assists": 0,
            "rated_appearances": 0,
            "appearances": 0,
            "average_rating": None,
            "goals_conceded": 0,
        }
    }
    worse = {"Alfa_Uno": {"average_rating": 5.5, "goals_conceded": 20}}
    names = ["Alfa Uno", "Alfa Dodici"]
    names += [f"Alfa {word}" for word in ("Due", "Tre", "Quattro", "Cinque", "Sei", "Sette", "Otto")]
    names += [
        f"Gamma {word}" for word in ("Due", "Tre", "Quattro", "Cinque", "Sei", "Sette", "Otto", "Dodici")
    ]
    names += [f"{club} {word}" for club in ("Beta", "Delta") for word in ("Nove", "Dieci", "Undici")]
    async with a_round(tmp_path, players=rows(**backup, **worse), squad=False) as here:
        await here.set_squad(*names)
        result = await here.ask()
    assert result["status"] == "lineup", result
    lineup = result["lineup"]
    [fielded] = [part for part in lineup["starters"] if part["role"] == "P"]
    [on_the_bench] = [part for part in lineup["bench"] if part["role"] == "P"]
    assert fielded["name"] == "Alfa Uno"
    assert on_the_bench["name"] == "Alfa Dodici"
    assert on_the_bench["value"] > fielded["value"]  # the likelier starter is fielded even with the lower key
    assert "plays exactly when Alfa Uno" in on_the_bench["reason"]
    for role in ("D", "C", "A"):
        places = [part for part in lineup["bench"] if part["role"] == role]
        values = [part["value"] for part in places]
        assert values == sorted(values, reverse=True)
        assert "first in" in places[0]["reason"]
        assert all("next" in part["reason"] for part in places[1:])
    labels = [source["label"] for source in lineup["sources"]]
    assert labels
    assert len(labels) == len(set(labels))
    assert len(lineup["starters"]) == 11


async def test_at6_what_each_starter_shows(tmp_path: Path) -> None:
    """R5.1: his match, chance of starting and its confidence, value, chance of scoring or clean sheet,
    penalties."""
    async with a_round(tmp_path) as here:
        lineup = (await here.ask())["lineup"]
    [keeper] = [part for part in lineup["starters"] if part["role"] == "P"]
    assert keeper["match"] in ("Alfa v Beta", "Gamma v Delta")
    assert keeper["p_clean_sheet"] is not None
    assert keeper["p_scores"] is None
    assert keeper["confidence"]["label"] == "agree"
    forward = next(part for part in lineup["starters"] if part["role"] == "A")
    assert forward["p_scores"] is not None
    assert forward["p_clean_sheet"] is None
    assert forward["value"] > 0
    takers = {part["name"] for part in [*lineup["starters"], *lineup["bench"]] if part["penalties"]}
    assert takers == {"Beta Nove", "Delta Nove"}
    assert forward["start_range"] is None  # the outlets agree
    assert lineup["likely_scorers"]
    chances = [entry["chance"] for entry in lineup["likely_scorers"]]
    assert chances == sorted(chances, reverse=True)
    assert lineup["expected"] == lineup["formations"][0]["mean"]
    assert lineup["low"] < lineup["expected"] < lineup["high"]
    assert [mark["points"] for mark in lineup["thresholds"]][:2] == [66, 72]
    assert lineup["bench_rule"]
    assert dt.datetime.fromisoformat(lineup["updated"]["newest"]) == NOW


async def test_at6_out_and_doubtful(tmp_path: Path) -> None:
    """R5.3: who's out or doubtful, and whether the bench covers him."""
    doubtful = FcoMatch("Alfa", "Beta", percents={"Beta Nove": (40, 60, 95, 50)})
    star = rows(Beta_Nove={"goals": 8, "average_rating": 7.2})
    async with a_round(tmp_path, matches=(doubtful, MATCHES[1]), players=star, squad=False) as here:
        await here.set_squad(*SQUAD, "Alfa Quattordici")  # the page lists him as out
        lineup = (await here.ask())["lineup"]
    concerns = {entry["name"]: entry for entry in lineup["out_and_doubtful"]}
    assert concerns["Alfa Quattordici"]["status"] == "out"
    assert concerns["Alfa Quattordici"]["covered_by"] is None  # he isn't in the eleven
    nove = next(part for part in lineup["starters"] if part["name"] == "Beta Nove")
    assert nove["confidence"]["label"] == "disputed"
    assert nove["start_range"] == [0.4, 0.95]
    assert concerns["Beta Nove"]["status"] == "doubtful"
    first_forward = next(part["name"] for part in lineup["bench"] if part["role"] == "A")
    assert concerns["Beta Nove"]["covered_by"] == first_forward
    assert set(concerns) == {"Alfa Quattordici", "Beta Nove"}


async def test_at6_won_t_play_is_his_reason(tmp_path: Path) -> None:
    async with a_round(tmp_path, squad=False) as here:
        await here.set_rules(bench_size=20)
        await here.set_squad(*SQUAD, "Alfa Quattordici")
        lineup = (await here.ask())["lineup"]
    place = next(part for part in lineup["bench"] if part["name"] == "Alfa Quattordici")
    assert place["reason"] == "won't play"


async def test_at6_disputed_is_doubtful_even_with_a_high_chance(tmp_path: Path) -> None:
    """They agree he's likely, but not how likely: that's still worth a mention."""
    disputed = FcoMatch("Alfa", "Beta", percents={"Beta Nove": (60, 95, 100, 100)})
    star = rows(Beta_Nove={"goals": 8, "average_rating": 7.2})
    async with a_round(tmp_path, matches=(disputed, MATCHES[1]), players=star) as here:
        lineup = (await here.ask())["lineup"]
    [entry] = [entry for entry in lineup["out_and_doubtful"] if entry["name"] == "Beta Nove"]
    assert entry["status"] == "doubtful"
    assert entry["p_start"] > 0.8


async def test_at6_before_the_lock(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        lineup = (await here.ask())["lineup"]
        assert dt.datetime.fromisoformat(lineup["lock"]).utcoffset() == dt.timedelta(hours=1)
        assert lineup["first_match"] == "Alfa v Beta"
        assert any("Alfa" in note and "first match" in note for note in lineup["check_before_lock"])


async def test_at9_same_facts_same_lineup_and_small(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        first = await here.ask()
        second = await here.ask(as_of=NOW.isoformat())
    assert first["lineup"]["formations"] == second["lineup"]["formations"]
    assert first["lineup"]["starters"] == second["lineup"]["starters"]
    assert len(json.dumps(first).encode()) < 15_000


def test_at9_fast() -> None:
    """In a process of its own, where the coverage tracer doesn't reach: see `tests/lineup_speed.py`."""
    result = run_command([sys.executable, "-m", "tests.lineup_speed"])
    assert result.returncode == 0, result.stderr
    assert float(result.stdout) < 3.0


async def test_at14_warnings_and_improve(tmp_path: Path) -> None:
    """One call gives the lineup, with a warning naming the match and what could improve it. Once better odds
    are submitted, the warning goes and the numbers use them."""
    bare = (FcoMatch("Alfa", "Beta", over3=""), MATCHES[1])
    unrated = {"rated_appearances": 0, "appearances": 0, "average_rating": None, "goals": 0, "assists": 0}
    async with a_round(tmp_path, matches=bare, players=rows(Alfa_Sei=unrated)) as here:
        first = await here.ask()
        assert first["status"] == "lineup", first
        lineup = first["lineup"]
        assert any("Alfa v Beta" in warning and "over/under" in warning for warning in lineup["warnings"])
        assert any("Alfa Sei" in warning and "no rated games" in warning for warning in lineup["warnings"])
        [item] = [item for item in lineup["improve"] if item["fact"] == "match_odds"]
        assert item["about"] == "Alfa v Beta"
        assert item["why"] == "partial"
        assert item["search"]
        before = next(part for part in [*lineup["starters"], *lineup["bench"]] if part["name"] == "Beta Nove")

        odds = await send(here.client, "submit_match_odds", odds_for("Alfa", "Beta"), NOW)
        assert not odds.is_error, odds
        here.clock.now = NOW + dt.timedelta(minutes=1)
        after = (await here.ask())["lineup"]
    assert not any("over/under" in warning for warning in after["warnings"])
    assert not [item for item in after["improve"] if item["fact"] == "match_odds"]
    now = next(part for part in [*after["starters"], *after["bench"]] if part["name"] == "Beta Nove")
    assert now["p_scores"] != before["p_scores"]


async def test_at14_a_player_no_outlet_lists_gets_his_warning(tmp_path: Path) -> None:
    extra = rows()
    extra.append(rows()[0] | {"player_id": 8999, "name": "Alfa Nessuno"})
    async with a_round(tmp_path, players=extra, squad=False) as here:
        await here.set_squad(*SQUAD, "Alfa Nessuno")
        lineup = (await here.ask())["lineup"]
    assert any("Alfa Nessuno" in warning and "default" in warning for warning in lineup["warnings"])
