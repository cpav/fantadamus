"""AT-7 of mvp-rules: the captain, by hand and over the simulated rounds (R3.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fantadamus.contracts.xy.league import FormulaRule
from fantadamus.engine.formula import Mark, choose_captain, formula_points
from tests.lineup_data import CAPTAIN_RULE, THREE_RULES
from tests.lineup_harness import Round, a_round
from tests.xy_harness import classic_with

pytestmark = pytest.mark.anyio

CAPTAIN = FormulaRule.model_validate(CAPTAIN_RULE)


def _points(vote: float) -> float:
    return formula_points(CAPTAIN, [], captain=Mark("A", vote, False))


def test_at7_the_table_by_hand() -> None:
    """By half points from -2.5 below 4 to +2.5 from 8.5, and nothing from 6 to 6.49."""
    votes = (3.5, 4.0, 4.49, 5.5, 6.0, 6.49, 6.5, 7.0, 8.49, 8.5, 9.5)
    assert [_points(vote) for vote in votes] == [-2.5, -2.0, -2.0, -0.5, 0.0, 0.0, 0.5, 1.0, 2.0, 2.5, 2.5]


def test_at7_the_vice_covers() -> None:
    """Three rounds: the captain rated; only the vice; neither, so the stand-in vote's points."""
    chosen = choose_captain([1, 2], {1: [2.0, None, None], 2: [0.5, 1.5, None]}, fallback=-1.0)
    assert (chosen.captain, chosen.vice, chosen.points) == (1, 2, [2.0, 1.5, -1.0])
    alone = choose_captain([1], {1: [2.0, None]}, fallback=0.0)
    assert (alone.captain, alone.vice, alone.points) == (1, None, [2.0, 0.0])


POINTS: dict[int, list[float | None]] = {
    1: [2.0, None, 1.0, None],
    2: [0.5, 1.5, None, None],
    3: [1.0, 1.0, 1.0, 1.0],
}


async def _with_captain(here: Round, *rules: dict[str, Any]) -> None:
    payload = classic_with(formula_rules=[*rules, CAPTAIN_RULE], lineup=None)
    result = await here.client.call_tool("set_league_rules", {"rules": payload})
    assert not result.is_error, result


async def _lineup(here: Round, **options: Any) -> dict[str, Any]:
    answer = await here.ask(**options)
    assert answer["status"] == "lineup", answer
    lineup: dict[str, Any] = answer["lineup"]
    return lineup


def _worth(lineup: dict[str, Any]) -> float:
    return next(float(rule["average"]) for rule in lineup["rules_worth"] if rule["name"] == "captain")


def test_at7_the_best_pair_by_hand() -> None:
    """1 with 3 as vice brings 5 over four rounds, more than any other pair; a tie goes to the first."""
    best = choose_captain([1, 2, 3], POINTS, fallback=-1.0)
    assert (best.captain, best.vice, sum(best.points)) == (1, 3, 5.0)
    assert choose_captain([1, 2, 3], POINTS, fallback=-1.0, named=2).points == [0.5, 1.5, 1.0, 1.0]
    level = choose_captain([7, 8, 9], {7: [1.0], 8: [1.0], 9: [1.0]}, fallback=0.0)
    assert (level.captain, level.vice) == (7, 8)


async def test_at7_the_recommended_captain_is_the_best(tmp_path: Path) -> None:
    """Over the tool's rounds, naming any other starter in the same formation brings no more."""
    async with a_round(tmp_path) as here:
        await _with_captain(here, *THREE_RULES)
        advised = await _lineup(here)
        assert advised["captain"] != advised["vice"]
        others = [player["name"] for player in advised["starters"] if player["name"] != advised["captain"]]
        for name in others[:4]:
            named = await _lineup(here, captain=name, formation=advised["formation"])
            assert named["captain"] == name
            assert _worth(named) <= _worth(advised)
            assert named["override"]["cost"] >= 0


async def test_at7_naming_another_gives_its_cost(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await _with_captain(here)
        advised = await _lineup(here)
        assert advised["override"] is None
        assert f"Captain {advised['captain']}, vice {advised['vice']}." in advised["message"]
        named = await _lineup(here, captain=advised["vice"])
        assert named["captain"] == advised["vice"]
        assert named["override"]["cost"] >= 0
        assert "costs" in named["message"]
        benched = next(player["name"] for player in advised["bench"] if player["role"] != "P")
        started = await _lineup(here, captain=benched)
        assert benched in [player["name"] for player in started["starters"]]
        unknown = await here.ask(captain="Nessuno Mai")
        assert unknown["status"] == "refused"
        logged = here.log.read()[-1]
        assert logged.captain is not None
    async with a_round(tmp_path / "none") as here:
        refused = await here.ask(captain="Alfa Nove")
    assert refused["status"] == "refused"
    assert "captain" in refused["message"]
