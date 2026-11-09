"""mvp-rules task 3.1: a formula rule in the simulation, where every round goes the same way: who it counts
after substitutions, what it adds, and the captain left for task 4 (design C5; R2.2, R3.2)."""

from __future__ import annotations

import pytest

from fantadamus.contracts.xy.league import Band, FormulaRule, Unit
from fantadamus.engine import keepers, outfield
from fantadamus.engine.lineup import arrange
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import SimPlayer, keeper_player, outfield_player, simulate
from tests.lineup_data import full_squad, lineup_rules
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

SCORING = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
SQUAD = full_squad()
NEVER_PLAYS = 4  # the best defender, a starter in every formation
RULES = lineup_rules()
ARRANGEMENTS = [arrange(SQUAD, formation, RULES) for formation in ("3-4-3", "4-4-2")]
DEFENDERS = FormulaRule(
    name="defenders",
    who=[Unit(role="D")],
    combine="each",
    bands=[Band(from_value=-100.0, points=0.5)],  # half a point for each defender fielded
)
CAPTAIN = FormulaRule(
    name="captain", who="captain", combine="each", stand_in=[7.0], bands=[Band(from_value=0.0, points=1.0)]
)


def _players() -> list[SimPlayer]:
    found: list[SimPlayer] = []
    for candidate in SQUAD:
        p_start = 0.0 if candidate.player_id == NEVER_PLAYS else 1.0
        if candidate.role == "P":
            inputs = keeper_inputs(name=candidate.name, club=candidate.club, p_start=p_start)
            found.append(
                keeper_player(candidate.player_id, inputs, keepers.value(inputs, SCORING), SCORING, None)
            )
        else:
            fielder = outfield_inputs(candidate.role, None, p_start=p_start, p_cameo=0.0)
            found.append(
                outfield_player(candidate.player_id, fielder, outfield.value(fielder, SCORING), SCORING, None)
            )
    return found


def test_a_rule_counts_the_substitute_and_adds_its_points() -> None:
    """The best defender never plays: the first defender on the bench comes on, and is counted."""
    players = _players()
    plain = simulate(players, [], ARRANGEMENTS, RULES, rounds=200)
    ruled = simulate(players, [], ARRANGEMENTS, RULES, formula_rules=[DEFENDERS, CAPTAIN], rounds=200)
    assert [result.rules for result in ruled] == [{"defenders": 1.5}, {"defenders": 2.0}]
    for before, after in zip(plain, ruled, strict=True):
        assert after.mean == pytest.approx(before.mean + after.rules["defenders"])
