"""mvp-lineup task 4.2: what a simulated player scores, worked out by hand (design C7; R4.2, R4.3)."""

from __future__ import annotations

import dataclasses
import math
import statistics
from typing import Any

import pytest

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.season import MantraRole
from fantadamus.engine import keepers, outfield
from fantadamus.engine.constants import (
    CAMEO_GOAL_VOTE,
    GOAL_VOTE_LIFT,
    KEEPER_BETA,
    KEEPER_VOTE_NOISE,
    VOTE_NOISE,
)
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import (
    Outfielder,
    draw_rounds,
    keeper_player,
    keeper_points,
    outfield_player,
    outfield_points,
)
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

SCORING = Scoring(goal=3, penalty_scored=2.5, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
_INPUTS = outfield_inputs("A", "Pc", team_xg=1.4, p_start=1.0, p_cameo=0.0)
_VALUE = outfield.value(_INPUTS, SCORING)
STRIKER = outfield_player(1, _INPUTS, _VALUE, SCORING, (0, 0))
_KEEPER_INPUTS = keeper_inputs(opponent_xg=1.4, p_start=1.0)
KEEPER = keeper_player(2, _KEEPER_INPUTS, keepers.value(_KEEPER_INPUTS, SCORING), SCORING, (0, 1))


def test_a_starters_points_by_hand() -> None:
    base = STRIKER.lowered_vote
    assert outfield_points(STRIKER, 0.0, 0, 0, 0, False) == pytest.approx(base)
    assert outfield_points(STRIKER, 0.3, 0, 0, 0, False) == pytest.approx(base + 0.3)
    assert outfield_points(STRIKER, 0.0, 1, 0, 0, False) == pytest.approx(base + GOAL_VOTE_LIFT + 3)
    assert outfield_points(STRIKER, 0.0, 0, 1, 0, False) == pytest.approx(base + GOAL_VOTE_LIFT + 2.5)
    assert outfield_points(STRIKER, 0.0, 0, 0, 1, False) == pytest.approx(base + 1)
    assert outfield_points(STRIKER, 0.0, 0, 0, 0, True) == pytest.approx(base - 0.5)
    assert outfield_points(STRIKER, 0.0, 2, 1, 1, True) == pytest.approx(
        base + 3 * GOAL_VOTE_LIFT + 2 * 3 + 2.5 + 1 - 0.5
    )


def test_his_vote_is_lowered_by_what_his_expected_goals_add_back() -> None:
    assert STRIKER.lowered_vote == pytest.approx(_VALUE.expected_vote - GOAL_VOTE_LIFT * _VALUE.e_goals)


def test_a_keepers_points_by_hand() -> None:
    skill = KEEPER.skill
    assert keeper_points(KEEPER, 0.0, 0) == pytest.approx(skill + 1)  # a clean sheet
    assert keeper_points(KEEPER, 0.2, 0) == pytest.approx(skill + 1.2)
    assert keeper_points(KEEPER, 0.0, 1) == pytest.approx(skill - KEEPER_BETA - 1)
    assert keeper_points(KEEPER, 0.0, 3) == pytest.approx(skill - 3 * KEEPER_BETA - 3)


def test_a_starter_gets_the_goals_and_assists_his_minutes_allow() -> None:
    """A bonus far above the noise lets each score show the count, so small differences in the rates show."""
    big = Scoring(goal=0, penalty_scored=0, assist=100, yellow=0, clean_sheet=0, goal_conceded=0)
    value = outfield.value(_INPUTS, big)
    player = outfield_player(1, _INPUTS, value, big, (0, 0))
    rounds = 20_000
    drawn = draw_rounds([player], [(1.4, 1.0)], rounds=rounds, seed=31)
    assists = sum(round((scores[1] or 0.0) / 100) for scores, _ in drawn)
    assert assists / rounds == pytest.approx(value.e_assists, abs=0.012)  # 5 standard errors


def _player(role: Role, mantra: MantraRole | None, **changes: Any) -> Outfielder:
    inputs = outfield_inputs(role, mantra, team_xg=1.4, p_start=1.0, p_cameo=0.0, **changes)
    return outfield_player(1, inputs, outfield.value(inputs, SCORING), SCORING, (0, 0))


def test_his_mantra_role_decides_how_a_cameo_is_priced() -> None:
    attacker = _player("A", "Pc")
    assert attacker.priced_cameo
    assert attacker.cameo_per_goal > 0
    for flat in (_player("C", "C"), _player("D", None), _player("A", "C")):
        assert (flat.priced_cameo, flat.cameo_per_goal) == (False, 0.0)


def test_a_takers_cameo_can_score_from_the_spot() -> None:
    """With no goals in the match, only a penalty can give a cameo a goal's value."""
    assert _player("A", "Pc", penalty_share=0.0).cameo_penalties == 0.0
    taker = dataclasses.replace(_player("A", "Pc", penalty_share=1.0), p_start=0.0, p_cameo=1.0)
    assert taker.cameo_penalties > 0.0
    rounds = 20_000
    drawn = draw_rounds([taker], [(0.0, 1.0)], rounds=rounds, seed=5)
    goals = sum(scores[1] == CAMEO_GOAL_VOTE + taker.scoring.goal for scores, _ in drawn)
    assert goals / rounds == pytest.approx(1 - math.exp(-taker.cameo_penalties), abs=0.01)


def test_how_much_a_rating_varies() -> None:
    """With no goals in the match and no cards, all that moves a starter's points is his rating's noise."""
    rounds = 5_000
    striker = dataclasses.replace(STRIKER, p_yellow=0.0)
    drawn = list(draw_rounds([striker, KEEPER], [(0.0, 0.0)], rounds=rounds, seed=9))
    assert statistics.stdev(scores[1] or 0.0 for scores, _ in drawn) == pytest.approx(VOTE_NOISE, rel=0.05)
    keeper = statistics.stdev(scores[2] or 0.0 for scores, _ in drawn)
    assert keeper == pytest.approx(KEEPER_VOTE_NOISE, rel=0.05)
