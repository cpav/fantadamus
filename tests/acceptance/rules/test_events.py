"""AT-1 to AT-4 of mvp-rules: one table of events (R1)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import EventRow, LeagueRules
from fantadamus.engine import keepers, outfield
from fantadamus.engine.outfield import OutfieldInputs
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import draw_rounds, keeper_player, outfield_player
from fantadamus.league.rules import CLASSIC, RulesStore, scoring_for
from tests.lineup_harness import LEAGUE, Round, a_round
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs
from tests.xy_harness import NOW

EARLIER: dict[str, Any] = {
    "goal": 3.0,
    "assist": 1.0,
    "penalty_scored": 3.0,
    "penalty_missed": -3.0,
    "penalty_saved": 3.0,
    "own_goal": -2.0,
    "yellow_card": -0.5,
    "red_card": -1.0,
    "goal_conceded": -1.0,
    "clean_sheet": 1.0,
}
# What the models read before this slice: the six values that were priced.
NOTHING = Scoring(goal=0, penalty_scored=0, assist=0, yellow=0, clean_sheet=0, goal_conceded=0)
PRICED_BEFORE = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
MISSED, SAVED = 0.15 * (1 - 0.78), 0.15 * (1 - 0.78) * 0.80
RED = {"P": 0.001, "D": 0.005, "C": 0.003, "A": 0.002}
OWN_GOAL = {"P": 0.001, "D": 0.005, "C": 0.001, "A": 0.001}


@pytest.mark.anyio
async def test_at1_stored_rules_differ_only_by_the_four(tmp_path: Path) -> None:
    """A user's file in the earlier form needs nothing entered again, and a lineup answers from it."""
    async with a_round(tmp_path, league=False) as here:
        path = RulesStore(here.store.root / "league").root / "user-1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        stored = {"user": "user-1", "saved_at": NOW.isoformat(), "rules": EARLIER | {"lineup": LEAGUE}}
        path.write_text(json.dumps(stored), encoding="utf-8")
        answer = await here.ask()
    assert answer["status"] == "lineup"

    rules = LeagueRules.model_validate(EARLIER)
    assert rules == CLASSIC  # the earlier form of Classic is Classic
    forward = outfield_inputs("A", "Pc", appearances=8, rated_appearances=8, average_rating=6.3)
    taker = forward.model_copy(update={"penalty_share": 1.0})
    defender = outfield_inputs("D", "Dc", appearances=8, rated_appearances=8, average_rating=6.1)
    minutes = {"A": 0.85, "D": 0.95}
    cases: list[tuple[OutfieldInputs, Role, float]] = [
        (forward, "A", 0.0),
        (taker, "A", MISSED * minutes["A"]),
        (defender, "D", 0.0),
    ]
    for who, role, missed in cases:
        now = outfield.value(who, scoring_for(rules, role))
        before = outfield.value(who, PRICED_BEFORE)
        four = -3 * missed - 1 * RED[role] - 2 * OWN_GOAL[role]
        assert now.e_start == pytest.approx(before.e_start + four)
    keeper = keeper_inputs()
    now_keeper = keepers.value(keeper, scoring_for(rules, "P"))
    before_keeper = keepers.value(keeper, PRICED_BEFORE)
    assert now_keeper.e_start == pytest.approx(
        before_keeper.e_start + 3 * SAVED - RED["P"] - 2 * OWN_GOAL["P"]
    )


async def _outlook(here: Round, player: str) -> dict[str, Any]:
    result = await here.client.call_tool("player_outlook", {"player": player})
    assert not result.is_error, result
    content = result.structured_content
    assert content is not None
    part: dict[str, Any] = content["answer"]["players"][0]
    return part


def test_at2_the_four_by_hand() -> None:
    """A first taker's miss at a league's own value, and each of the others on its own."""
    rows = [EventRow(event="penalty_missed", points=-2.5, roles=["A"])]
    only_missed = scoring_for(LeagueRules(events=rows), "A")
    taker = outfield_inputs("A", "Pc", penalty_share=1.0, p_start=1.0, p_cameo=0.0)
    without = outfield.value(taker, NOTHING)
    assert outfield.value(taker, only_missed).e_start == pytest.approx(without.e_start - 2.5 * MISSED * 0.85)
    half = taker.model_copy(update={"penalty_share": 0.5})
    assert outfield.value(half, only_missed).e_start == pytest.approx(
        without.e_start - 2.5 * MISSED * 0.85 * 0.5
    )

    saves = scoring_for(LeagueRules(events=[EventRow(event="penalty_saved", points=2.5, roles=["P"])]), "P")
    keeper = keeper_inputs()
    nothing = keepers.value(keeper, NOTHING)
    assert keepers.value(keeper, saves).e_start == pytest.approx(nothing.e_start + 2.5 * SAVED)

    red = scoring_for(LeagueRules(events=[EventRow(event="red_card", points=-1.0, roles=["D"])]), "D")
    defender = outfield_inputs("D", "Dc", p_start=1.0, p_cameo=0.0)
    plain = outfield.value(defender, NOTHING)
    assert outfield.value(defender, red).e_start == pytest.approx(plain.e_start - RED["D"])

    own = scoring_for(LeagueRules(events=[EventRow(event="own_goal", points=-2.0, roles=["D"])]), "D")
    assert outfield.value(defender, own).e_start == pytest.approx(plain.e_start - 2 * OWN_GOAL["D"])


def test_at3_a_defenders_clean_sheet() -> None:
    """His value rises by that chance times the points, on the same simulated goals as his keeper."""
    rules = LeagueRules(events=[EventRow(event="clean_sheet", points=2.0, roles=["P", "D"])])
    scoring = scoring_for(rules, "D")
    plain = outfield_inputs("D", "Dc", opponent_xg=1.1, p_start=1.0, p_cameo=0.0)
    value = outfield.value(plain, scoring)
    assert value.e_start == pytest.approx(outfield.value(plain, NOTHING).e_start + 2.0 * math.exp(-1.1))

    defender = outfield_player(1, plain, value, scoring, (0, 0))
    keeper = keeper_inputs(opponent_xg=1.1, p_start=1.0)
    his = scoring_for(rules, "P")
    guard = keeper_player(2, keeper, keepers.value(keeper, his), his, (0, 0))
    with_goals: list[float] = []
    without_goals: list[float] = []
    for scores, goals in draw_rounds([defender, guard], [(1.0, 1.1)], rounds=4000, seed=23):
        score = scores[1]
        assert score is not None
        (without_goals if goals[0][1] == 0 else with_goals).append(score)
    assert sum(without_goals) / len(without_goals) - sum(with_goals) / len(with_goals) == pytest.approx(
        2.0, abs=0.1
    )


@pytest.mark.anyio
async def test_at3_through_the_tools(tmp_path: Path) -> None:
    """The row reaches a real answer: his value uses his match's opponents, and only his role's change."""
    defenders_too = CLASSIC.model_dump()
    defenders_too["events"].append({"event": "clean_sheet", "points": 2.0, "roles": ["D"]})
    async with a_round(tmp_path / "classic") as here:
        before = await _outlook(here, "Alfa Due")
        before_midfielder = await _outlook(here, "Alfa Sei")
    async with a_round(tmp_path / "rows") as here:
        result = await here.client.call_tool("set_league_rules", {"rules": defenders_too})
        assert not result.is_error, result
        after = await _outlook(here, "Alfa Due")
        after_midfielder = await _outlook(here, "Alfa Sei")
    chance = math.exp(-after["opponent_xg"])
    assert after["value"]["e_start"] == pytest.approx(before["value"]["e_start"] + 2.0 * chance)
    assert after_midfielder["value"]["e_start"] == pytest.approx(before_midfielder["value"]["e_start"])


def test_at3_a_goal_per_role_still_works() -> None:
    rules = LeagueRules(
        events=[
            EventRow(event="goal", points=5.0, roles=["D"]),
            EventRow(event="goal", points=3.0, roles=["A"]),
        ]
    )
    who = outfield_inputs("D", "Dc", team_xg=1.4)
    low = outfield.value(who, scoring_for(rules, "A"))
    high = outfield.value(who, scoring_for(rules, "D"))
    assert high.e_start - low.e_start == pytest.approx(2.0 * high.e_goals)


def test_at4_share_events_by_hand() -> None:
    """A decisive goal adds its share of the points to every goal; a set-piece assist replaces its share."""
    rules = LeagueRules(
        events=[
            EventRow(event="goal", points=3.0, roles=["A"]),
            EventRow(event="penalty_scored", points=3.0, roles=["A"]),
            EventRow(event="assist", points=1.0, roles=["A"]),
            EventRow(event="decisive_goal", points=1.0, roles=["A"]),
            EventRow(event="set_piece_assist", points=0.5, roles=["A"]),
        ]
    )
    scoring = scoring_for(rules, "A")
    assert scoring.goal == pytest.approx(3 + 0.20 * 1)
    assert scoring.penalty_scored == pytest.approx(3 + 0.20 * 1)
    assert scoring.assist == pytest.approx(0.75 * 1 + 0.25 * 0.5)
    without = scoring_for(LeagueRules(events=[EventRow(event="assist", points=1.0, roles=["A"])]), "A")
    assert without.assist == 1
