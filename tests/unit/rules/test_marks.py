"""mvp-rules task 3.1: each rated player's mark, the pure vote a formula rule reads (design C5; R2.2)."""

from __future__ import annotations

import dataclasses

import pytest

from fantadamus.engine import keepers, outfield
from fantadamus.engine.constants import CAMEO_FLAT, CAMEO_GOAL_VOTE, CAMEO_RATING
from fantadamus.engine.formula import Mark
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import SimPlayer, draw_marked, draw_rounds, keeper_player, outfield_player
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

GOALS_ONLY = Scoring(goal=3, penalty_scored=3, assist=0, yellow=0, clean_sheet=1, goal_conceded=-1)
_STRIKER = outfield_inputs("A", "Pc", team_xg=1.4, p_start=0.8, p_cameo=0.1, penalty_share=1.0)
STRIKER = outfield_player(1, _STRIKER, outfield.value(_STRIKER, GOALS_ONLY), GOALS_ONLY, (0, 0))
_KEEPER = keeper_inputs(opponent_xg=1.2, p_start=1.0)
KEEPER = keeper_player(2, _KEEPER, keepers.value(_KEEPER, GOALS_ONLY), GOALS_ONLY, (0, 1))
MATCH = [(1.4, 1.2)]


def test_a_starters_mark_is_his_score_without_the_events() -> None:
    striker = dataclasses.replace(STRIKER, p_start=1.0, p_cameo=0.0, rare=0.0)
    keeper = dataclasses.replace(KEEPER, rare=0.0)
    scorers = 0
    for scores, goals, marks in draw_marked([striker, keeper], MATCH, rounds=400, seed=3, marking=True):
        scored = round(((scores[1] or 0.0) - marks[1].vote) / 3)  # only goals move his points
        assert (marks[1].role, marks[1].bonus_or_goal) == ("A", scored > 0)
        assert marks[1].vote == pytest.approx((scores[1] or 0.0) - 3 * scored)
        scorers += scored > 0
        conceded = goals[0][0]
        events = 1.0 if conceded == 0 else -conceded
        assert (marks[2].role, marks[2].bonus_or_goal) == ("P", conceded > 0)
        assert marks[2].vote == pytest.approx((scores[2] or 0.0) - events)
    assert 0 < scorers < 400


def test_a_cameos_mark() -> None:
    """A rated cameo, a cameo with a goal, or a flat one; without a rating, no mark."""
    attacker = dataclasses.replace(STRIKER, p_start=0.0, p_cameo=1.0)
    seen = set()
    for scores, _, marks in draw_marked([attacker], MATCH, rounds=400, seed=5, marking=True):
        if scores[1] is None:
            assert marks == {}
        elif scores[1] == CAMEO_RATING:
            assert marks[1] == Mark("A", CAMEO_RATING, False)
        else:
            assert marks[1] == Mark("A", CAMEO_GOAL_VOTE, True)
        seen.add(marks[1].vote if marks else None)
    assert seen == {None, CAMEO_RATING, CAMEO_GOAL_VOTE}
    flat = dataclasses.replace(attacker, priced_cameo=False, role="C")
    for _, _, marks in draw_marked([flat], MATCH, rounds=20, seed=5, marking=True):
        assert marks == {1: Mark("C", CAMEO_FLAT, False)}


def test_marking_changes_no_round() -> None:
    players: list[SimPlayer] = [STRIKER, KEEPER]
    marked = [
        (scores, goals) for scores, goals, _ in draw_marked(players, MATCH, rounds=300, seed=7, marking=True)
    ]
    assert marked == list(draw_rounds(players, MATCH, rounds=300, seed=7))
    assert all(marks == {} for _, _, marks in draw_marked(players, MATCH, rounds=5, seed=7, marking=False))


def test_a_defender_reads_his_own_matchs_goals_against() -> None:
    """Two matches: only the first has goals, and neither defender plays in it, so both keep a clean sheet."""
    defender = outfield_inputs("D", None, team_xg=1.0, opponent_xg=1.0, p_start=1.0, p_cameo=0.0)
    value = outfield.value(defender, GOALS_ONLY)
    home = dataclasses.replace(
        outfield_player(1, defender, value, GOALS_ONLY, (1, 0)), p_yellow=0.0, rare=0.0
    )
    away = dataclasses.replace(home, player_id=2, side=(1, 1))
    assert home.defends
    goals = [(0.0, 3.0), (0.0, 0.0)]
    for scores, _, marks in draw_marked([home, away], goals, rounds=100, seed=11, marking=True):
        for player in (1, 2):
            assert (scores[player] or 0.0) - marks[player].vote == pytest.approx(1.0)  # his clean sheet
