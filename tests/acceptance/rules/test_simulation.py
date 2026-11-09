"""AT-8, AT-9 and AT-12 of mvp-rules: formula rules in the simulated rounds and the answer (R2.2, R3.1,
R3.2, R3.4, R5.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts.checks._common import run_command

from tests.lineup_data import THREE_RULES
from tests.lineup_harness import Round, a_round
from tests.xy_harness import NOW, classic_with

pytestmark = pytest.mark.anyio

KEEPER_BONUS: dict[str, Any] = {
    "name": "keeper bonus",
    "who": [{"role": "P"}],
    "combine": "each",
    "bands": [{"from_value": 0.0, "points": 6.0}],
}


def _rewarding(defenders: str, count: int) -> dict[str, Any]:
    """A large bonus for fielding few or many defenders, enough to decide the formation."""
    return {
        "name": "defence count",
        "who": [{"role": "D", defenders: count}],
        "combine": "average",
        "bands": [{"from_value": 0.0, "points": 10.0}],
    }


async def _with(here: Round, *rules: dict[str, Any], **lineup: Any) -> None:
    payload = classic_with(formula_rules=list(rules), lineup=lineup or None)
    result = await here.client.call_tool("set_league_rules", {"rules": payload})
    assert not result.is_error, result


async def _lineup(here: Round, **options: Any) -> dict[str, Any]:
    answer = await here.ask(**options)
    assert answer["status"] == "lineup", answer
    lineup: dict[str, Any] = answer["lineup"]
    return lineup


def _worth(lineup: dict[str, Any], name: str) -> float:
    return next(float(rule["average"]) for rule in lineup["rules_worth"] if rule["name"] == name)


async def test_at8_a_rules_points_reach_the_fantasy_goals(tmp_path: Path) -> None:
    """Over the same rounds, a formation's expected score rises by exactly what the rule gave in it."""
    async with a_round(tmp_path / "plain") as here:
        plain = await _lineup(here)
    async with a_round(tmp_path / "bonus") as here:
        await _with(here, KEEPER_BONUS)
        bonus = await _lineup(here)
    worth = _worth(bonus, "keeper bonus")
    assert 5.5 < worth <= 6.0  # a keeper is fielded almost every round, his backup covering
    before = next(result for result in plain["formations"] if result["formation"] == bonus["formation"])
    assert bonus["expected"] == pytest.approx(before["mean"] + worth, abs=0.02)
    reached_before = {mark["points"]: mark["chance"] for mark in before["thresholds"]}
    assert all(mark["chance"] >= reached_before[mark["points"]] for mark in bonus["thresholds"])


async def test_at8_a_modifier_can_change_the_formation(tmp_path: Path) -> None:
    async with a_round(tmp_path / "few") as here:
        await _with(here, _rewarding("at_most", 3))
        few = await _lineup(here)
    async with a_round(tmp_path / "many") as here:
        await _with(here, _rewarding("at_least", 5))
        many = await _lineup(here)
    assert few["formation"].startswith("3-")
    assert many["formation"].startswith("5-")


async def test_at8_a_total_points_league(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await _with(here, KEEPER_BONUS, format="total_points")
        lineup = await _lineup(here)
    assert 5.5 < _worth(lineup, "keeper bonus") <= 6.0


async def test_at9_each_rules_worth_is_in_the_answer(tmp_path: Path) -> None:
    """Named and bounded in the answer, logged with the decision, and the same for the same facts."""
    async with a_round(tmp_path) as here:
        await _with(here, KEEPER_BONUS, _rewarding("at_most", 3))
        first = await _lineup(here)
        again = await _lineup(here, as_of=NOW.isoformat())
        [*_, logged] = here.log.read()
    assert {rule["name"] for rule in first["rules_worth"]} == {"keeper bonus", "defence count"}
    assert first["rules_worth"] == again["rules_worth"]
    assert first["expected"] == again["expected"]
    assert logged.rules_worth == {rule["name"]: rule["average"] for rule in first["rules_worth"]}
    assert not any(
        "doesn't include" in warning and "keeper bonus" in warning for warning in first["warnings"]
    )


async def test_at9_an_overrides_cost_includes_the_rules(tmp_path: Path) -> None:
    """Fielding four defenders gives up the bonus for three, and the cost says so."""
    async with a_round(tmp_path) as here:
        await _with(here, _rewarding("at_most", 3))
        chosen = await _lineup(here, formation="4-3-3")
    override = chosen["override"]
    assert override["advised_formation"].startswith("3-")
    assert override["cost"] > 9.0


async def test_at12_a_squad_with_rules_stays_in_budget(tmp_path: Path) -> None:
    """Three modifiers, in a process of its own for the time: see `tests/lineup_speed.py`."""
    result = run_command([sys.executable, "-m", "tests.lineup_speed", "--rules"])
    assert result.returncode == 0, result.stderr
    assert float(result.stdout) < 3.0
    async with a_round(tmp_path) as here:
        await _with(here, *THREE_RULES)
        answer = await here.ask()
    assert len(json.dumps(answer).encode()) < 15_000
